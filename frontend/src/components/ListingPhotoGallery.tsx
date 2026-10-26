import type { ListingPhoto } from '../types'

export function ListingPhotoGallery({ photos }: { photos: ListingPhoto[] }) {
  if (photos.length === 0) {
    return <p className="muted">No photos yet.</p>
  }
  const ordered = [...photos].sort((left, right) => left.position - right.position)
  return (
    <div className="photo-gallery">
      {ordered.map((photo, index) => (
        <figure className={index === 0 ? 'photo-main' : 'photo-thumb'} key={photo.id}>
          <img src={photo.url} alt={`Parking photo ${index + 1}`} loading="lazy" />
          {photo.is_cover ? <figcaption>Cover photo</figcaption> : null}
        </figure>
      ))}
    </div>
  )
}
