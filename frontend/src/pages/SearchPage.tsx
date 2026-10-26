import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Map as LeafletMap } from 'leaflet'
import { Link } from 'react-router-dom'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Rectangle,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet'
import { errorMessage, searchParking } from '../lib/api'
import { TILE_ATTRIBUTION, TILE_URL } from '../lib/env'
import { formatPriceSummary, formatVehicleTypes } from '../lib/listingFormat'
import {
  VEHICLE_TYPES,
  type ParkingSearchItem,
  type ParkingSearchRequest,
  type ParkingSearchResponse,
  type SearchSort,
  type VehicleType,
} from '../types'

const DEFAULT_CENTER = { lat: 19.9975, lng: 73.7898 }
const DEFAULT_ZOOM = 13
const MAX_BBOX_SPAN_DEGREES = 0.5
const PAGE_SIZE = 12

const INITIAL_REQUEST: ParkingSearchRequest = {
  lat: DEFAULT_CENTER.lat,
  lng: DEFAULT_CENTER.lng,
  radius_m: 2000,
  sort: 'distance',
  limit: PAGE_SIZE,
}

interface Filters {
  radius_m: number
  vehicle_type: VehicleType | ''
  covered: '' | 'true' | 'false'
  maxPriceRupees: string
  sort: SearchSort
}

const INITIAL_FILTERS: Filters = {
  radius_m: 2000,
  vehicle_type: '',
  covered: '',
  maxPriceRupees: '',
  sort: 'distance',
}

function filtersToRequest(filters: Filters): ParkingSearchRequest {
  const request: ParkingSearchRequest = { sort: filters.sort, limit: PAGE_SIZE }
  if (filters.vehicle_type) {
    request.vehicle_type = filters.vehicle_type
  }
  if (filters.covered) {
    request.covered = filters.covered === 'true'
  }
  const maxPrice = Number(filters.maxPriceRupees)
  if (filters.maxPriceRupees.trim() && Number.isFinite(maxPrice) && maxPrice >= 0) {
    request.max_price_paise = Math.round(maxPrice * 100)
  }
  return request
}

function formatDistance(distanceM: number): string {
  if (distanceM < 1000) {
    return `${Math.round(distanceM)} m away`
  }
  return `${(distanceM / 1000).toFixed(1)} km away`
}

function MapBridge({ onMapReady }: { onMapReady: (map: LeafletMap) => void }) {
  const map = useMap()
  useEffect(() => {
    onMapReady(map)
  }, [map, onMapReady])
  return null
}

function MapViewport({ result }: { result: ParkingSearchResponse | null }) {
  const map = useMap()
  const mode = result?.mode
  const bbox = result?.bbox
  const centerLatitude = result?.center_latitude
  const centerLongitude = result?.center_longitude

  useEffect(() => {
    if (!mode || centerLatitude === undefined || centerLongitude === undefined) {
      return
    }
    if (mode === 'bbox' && bbox && bbox.length === 4) {
      map.fitBounds(
        [
          [bbox[1], bbox[0]],
          [bbox[3], bbox[2]],
        ],
        { padding: [24, 24], maxZoom: 15 },
      )
      return
    }
    map.setView([centerLatitude, centerLongitude], Math.max(map.getZoom(), DEFAULT_ZOOM))
  }, [map, mode, bbox, centerLatitude, centerLongitude])

  return null
}

function SelectedFocus({ item }: { item: ParkingSearchItem | undefined }) {
  const map = useMap()
  useEffect(() => {
    if (item) {
      map.panTo([item.latitude, item.longitude], { animate: true })
    }
  }, [map, item])
  return null
}

function SearchMap({
  result,
  selectedId,
  onSelect,
  onMapReady,
}: {
  result: ParkingSearchResponse | null
  selectedId: string | null
  onSelect: (id: string) => void
  onMapReady: (map: LeafletMap) => void
}) {
  const center: [number, number] = result
    ? [result.center_latitude, result.center_longitude]
    : [DEFAULT_CENTER.lat, DEFAULT_CENTER.lng]
  const selectedItem = result?.items.find((item) => item.id === selectedId)

  return (
    <div className="search-map" role="region" aria-label="Map of parking search results">
      <MapContainer center={center} zoom={DEFAULT_ZOOM} scrollWheelZoom className="map-canvas">
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        <MapBridge onMapReady={onMapReady} />
        <MapViewport result={result} />
        <SelectedFocus item={selectedItem} />
        {result?.mode === 'radius' && result.radius_m !== null ? (
          <Circle
            center={[result.center_latitude, result.center_longitude]}
            radius={result.radius_m}
            pathOptions={{ color: '#3f6a55', fillColor: '#c8f27b', fillOpacity: 0.08 }}
          />
        ) : null}
        {result?.bbox && result.bbox.length === 4 ? (
          <Rectangle
            bounds={[
              [result.bbox[1], result.bbox[0]],
              [result.bbox[3], result.bbox[2]],
            ]}
            pathOptions={{ color: '#3f6a55', fillOpacity: 0.04 }}
          />
        ) : null}
        {result?.items.map((item) => (
          <CircleMarker
            key={item.id}
            center={[item.latitude, item.longitude]}
            radius={item.id === selectedId ? 11 : 8}
            pathOptions={{
              color: item.id === selectedId ? '#0d1914' : '#29463a',
              fillColor: item.id === selectedId ? '#c8f27b' : '#3f6a55',
              fillOpacity: 0.92,
            }}
            eventHandlers={{ click: () => onSelect(item.id) }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              {item.title} · {formatDistance(item.distance_m)}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
      <p className="map-attribution">
        Map data ©{' '}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          OpenStreetMap
        </a>{' '}
        contributors · Pins are approximate.
      </p>
    </div>
  )
}

export function SearchPage() {
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS)
  const [params, setParams] = useState<ParkingSearchRequest>(INITIAL_REQUEST)
  const [result, setResult] = useState<ParkingSearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const requestSequence = useRef(0)
  const mapRef = useRef<LeafletMap | null>(null)

  useEffect(() => {
    const sequence = requestSequence.current + 1
    requestSequence.current = sequence
    searchParking(params)
      .then((response) => {
        if (requestSequence.current === sequence) {
          setResult(response)
        }
      })
      .catch((loadError: unknown) => {
        if (requestSequence.current === sequence) {
          setError(errorMessage(loadError))
        }
      })
      .finally(() => {
        if (requestSequence.current === sequence) {
          setLoading(false)
        }
      })
  }, [params])

  const handleMapReady = useCallback((map: LeafletMap) => {
    mapRef.current = map
  }, [])

  function applyParams(nextParams: ParkingSearchRequest) {
    setLoading(true)
    setLoadingMore(false)
    setError(null)
    setResult(null)
    setSelectedId(null)
    setParams(nextParams)
  }

  function handleApply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    applyParams({
      lat: DEFAULT_CENTER.lat,
      lng: DEFAULT_CENTER.lng,
      radius_m: filters.radius_m,
      ...filtersToRequest(filters),
    })
  }

  function handleSearchArea() {
    const map = mapRef.current
    if (!map) {
      return
    }
    const bounds = map.getBounds()
    const west = bounds.getWest()
    const south = bounds.getSouth()
    const east = bounds.getEast()
    const north = bounds.getNorth()
    if (
      Math.abs(east - west) > MAX_BBOX_SPAN_DEGREES ||
      Math.abs(north - south) > MAX_BBOX_SPAN_DEGREES
    ) {
      setError('Zoom in a little further before searching this map area.')
      return
    }
    applyParams({
      bbox: [west, south, east, north].map((value) => value.toFixed(6)).join(','),
      ...filtersToRequest(filters),
    })
  }

  async function handleLoadMore() {
    if (!result?.next_cursor || loadingMore) {
      return
    }
    const sequence = requestSequence.current
    setLoadingMore(true)
    setError(null)
    try {
      const response = await searchParking({ ...params, cursor: result.next_cursor })
      if (requestSequence.current !== sequence) {
        return
      }
      setResult((current) =>
        current ? { ...response, items: [...current.items, ...response.items] } : response,
      )
    } catch (loadError) {
      if (requestSequence.current === sequence) {
        setError(errorMessage(loadError))
      }
    } finally {
      if (requestSequence.current === sequence) {
        setLoadingMore(false)
      }
    }
  }

  return (
    <section className="page-stack search-page">
      <header className="page-header search-header">
        <div>
          <p className="eyebrow">Nashik · discovery demo</p>
          <h1>Find parking in Nashik</h1>
          <p className="lede">
            Search active private parking by distance, price, covered parking, and vehicle fit.
            Every map pin is deliberately approximate.
          </p>
        </div>
      </header>

      <form className="panel search-form" onSubmit={handleApply}>
        <div className="search-field-grid">
          <label className="field">
            Radius
            <select
              value={filters.radius_m}
              onChange={(event) =>
                setFilters((current) => ({ ...current, radius_m: Number(event.target.value) }))
              }
            >
              <option value={500}>500 m</option>
              <option value={1000}>1 km</option>
              <option value={2000}>2 km</option>
              <option value={3000}>3 km</option>
              <option value={5000}>5 km</option>
              <option value={10000}>10 km</option>
            </select>
          </label>
          <label className="field">
            Vehicle
            <select
              value={filters.vehicle_type}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  vehicle_type: event.target.value as VehicleType | '',
                }))
              }
            >
              <option value="">Any vehicle</option>
              {VEHICLE_TYPES.map((vehicle) => (
                <option key={vehicle.value} value={vehicle.value}>
                  {vehicle.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Covered
            <select
              value={filters.covered}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  covered: event.target.value as Filters['covered'],
                }))
              }
            >
              <option value="">Any</option>
              <option value="true">Covered only</option>
              <option value="false">Open only</option>
            </select>
          </label>
          <label className="field">
            Max hourly price (₹)
            <input
              type="number"
              min="0"
              step="1"
              inputMode="numeric"
              placeholder="No limit"
              value={filters.maxPriceRupees}
              onChange={(event) =>
                setFilters((current) => ({ ...current, maxPriceRupees: event.target.value }))
              }
            />
          </label>
          <label className="field">
            Sort by
            <select
              value={filters.sort}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  sort: event.target.value as SearchSort,
                }))
              }
            >
              <option value="distance">Distance</option>
              <option value="price">Price</option>
            </select>
          </label>
        </div>
        <div className="header-actions">
          <button className="button" type="submit" disabled={loading}>
            {loading ? 'Searching…' : 'Apply search'}
          </button>
          <button
            className="button button-secondary"
            type="button"
            onClick={handleSearchArea}
            disabled={loading}
          >
            Search this map area
          </button>
        </div>
      </form>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="search-layout">
        <div className="search-results" aria-live="polite">
          <div className="search-results-heading">
            <div>
              <p className="eyebrow">Approximate matches</p>
              <h2>
                {result ? `${result.items.length} parking spaces` : 'Search results'}
                {result?.next_cursor ? '+' : ''}
              </h2>
            </div>
            {result ? (
              <p className="search-mode-note">
                {result.mode === 'radius'
                  ? `Within ${((result.radius_m ?? 0) / 1000).toFixed(1)} km of the demo center`
                  : 'Inside the visible map area'}
              </p>
            ) : null}
          </div>
          <p className="muted search-disclaimer">
            Distances are measured from the search center to each approximate pin. Exact addresses
            and access details stay private.
          </p>

          {loading ? (
            <p className="status-message" role="status">
              Searching active parking…
            </p>
          ) : null}

          {!loading && result && result.items.length === 0 ? (
            <div className="panel empty-panel">
              <h3>No active parking matched</h3>
              <p className="muted">Try a wider radius, fewer filters, or search the visible map.</p>
            </div>
          ) : null}

          <div className="search-result-list">
            {result?.items.map((item) => (
              <article
                className={
                  item.id === selectedId
                    ? 'card listing-card search-result-card search-result-card-selected'
                    : 'card listing-card search-result-card'
                }
                key={item.id}
              >
                <div className="listing-card-cover">
                  {item.cover_url ? (
                    <img src={item.cover_url} alt="" loading="lazy" />
                  ) : (
                    <span>No photo yet</span>
                  )}
                </div>
                <div className="listing-card-body">
                  <div className="listing-card-heading">
                    <h3>
                      <Link to={`/parking/${item.id}`}>{item.title}</Link>
                    </h3>
                    <span className="badge">{formatDistance(item.distance_m)}</span>
                  </div>
                  <p className="muted">
                    {item.locality}, {item.city}, {item.state}
                  </p>
                  <p className="listing-price">{formatPriceSummary(item.parking)}</p>
                  <p className="muted search-result-meta">
                    {formatVehicleTypes(item.parking.supported_vehicle_types)} ·{' '}
                    {item.parking.is_covered ? 'Covered' : 'Open'} ·{' '}
                    {item.parking.parking_type.replaceAll('_', ' ')}
                  </p>
                  <div className="card-actions">
                    <button
                      className="button button-secondary button-small"
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                    >
                      Show on map
                    </button>
                    <Link className="button button-quiet button-small" to={`/parking/${item.id}`}>
                      View details
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>

          {result?.next_cursor ? (
            <button
              className="button button-secondary"
              type="button"
              onClick={handleLoadMore}
              disabled={loadingMore}
            >
              {loadingMore ? 'Loading more…' : 'Load more parking'}
            </button>
          ) : null}
        </div>

        <div className="search-map-column">
          <SearchMap
            result={result}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onMapReady={handleMapReady}
          />
          <p className="muted search-map-note">
            Pan or zoom the map, then choose “Search this map area” for a bounding-box search. Map
            tiles come directly from OpenStreetMap.
          </p>
        </div>
      </div>
    </section>
  )
}
