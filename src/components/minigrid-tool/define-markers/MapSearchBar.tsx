'use client';

import React, { useEffect, useId, useRef, useState } from 'react';

interface MapSearchBarProps {
  map: google.maps.Map | null;
  onPlaceSelected: (_lat: number, _lng: number, _name: string) => void;
  placeholder?: string;
  className?: string;
}

export default function MapSearchBar({
  map,
  onPlaceSelected,
  placeholder = 'Search for a location or address...',
  className = '',
}: MapSearchBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const autocompleteRef =
    useRef<google.maps.places.PlaceAutocompleteElement | null>(null);
  const onPlaceSelectedRef = useRef(onPlaceSelected);
  const labelId = useId();
  const [error, setError] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [manualCoordinates, setManualCoordinates] = useState('');

  useEffect(() => {
    onPlaceSelectedRef.current = onPlaceSelected;
  }, [onPlaceSelected]);

  useEffect(() => {
    if (autocompleteRef.current) {
      autocompleteRef.current.placeholder = placeholder;
    }
  }, [placeholder]);

  useEffect(() => {
    const container = containerRef.current;
    if (!map || !window.google?.maps?.importLibrary || !container) return;

    let disposed = false;
    let selectionId = 0;
    let autocomplete: google.maps.places.PlaceAutocompleteElement | null = null;
    let boundsListener: google.maps.MapsEventListener | undefined;

    setError(null);
    setIsReady(false);

    const handleSelect = async (
      event: google.maps.places.PlacePredictionSelectEvent
    ) => {
      const currentSelectionId = ++selectionId;
      const place = event.placePrediction.toPlace();

      try {
        await place.fetchFields({
          fields: ['location', 'displayName', 'formattedAddress'],
        });
      } catch (fetchError) {
        if (disposed || currentSelectionId !== selectionId) return;
        console.error('Failed to fetch selected place details:', fetchError);
        setError('Could not load that location. Please select it again.');
        return;
      }

      if (disposed || currentSelectionId !== selectionId) return;

      if (!place.location) {
        setError("Sorry, we couldn't find location details for that place.");
        return;
      }

      const lat = place.location.lat();
      const lng = place.location.lng();
      const name =
        place.displayName ||
        place.formattedAddress?.split(',')[0] ||
        'New Location';

      map.panTo({ lat, lng });
      if ((map.getZoom() ?? 0) < 16) {
        map.setZoom(17);
      }

      onPlaceSelectedRef.current(lat, lng, name);
      if (autocomplete) autocomplete.value = '';
    };

    const handleRequestError = (requestError: Event) => {
      ++selectionId;
      console.error('Place autocomplete request failed:', requestError);
      setError(
        'Location search is unavailable. Verify that Places API (New) is enabled for this Maps API key.'
      );
    };

    const initialize = async () => {
      try {
        const { PlaceAutocompleteElement } =
          await google.maps.importLibrary('places');

        if (disposed) return;

        autocomplete = new PlaceAutocompleteElement({ placeholder });
        autocomplete.className =
          'block w-full rounded-xl border border-zinc-300 bg-white text-base text-zinc-900 dark:border-zinc-600 dark:bg-zinc-800 dark:text-white';
        autocomplete.setAttribute('aria-labelledby', labelId);
        autocomplete.addEventListener('gmp-select', handleSelect);
        autocomplete.addEventListener('gmp-error', handleRequestError);

        const updateLocationBias = () => {
          if (autocomplete) {
            autocomplete.locationBias = map.getBounds() ?? null;
          }
        };
        updateLocationBias();
        boundsListener = map.addListener('bounds_changed', updateLocationBias);

        autocompleteRef.current = autocomplete;
        container.appendChild(autocomplete);
        setIsReady(true);
      } catch (libraryError) {
        if (disposed) return;
        console.error('Failed to load the Places library:', libraryError);
        setError(
          'Could not load location search. Please reload the page and try again.'
        );
      }
    };

    void initialize();

    return () => {
      disposed = true;
      boundsListener?.remove();
      autocomplete?.removeEventListener('gmp-select', handleSelect);
      autocomplete?.removeEventListener('gmp-error', handleRequestError);
      autocomplete?.remove();
      autocompleteRef.current = null;
    };
  }, [map, placeholder, labelId]);

  const handleManualCoordinatesSubmit = (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();
    const coordinates = manualCoordinates
      .trim()
      .split(/[,\s]+/)
      .filter(Boolean);
    const lat = Number(coordinates[0]);
    const lng = Number(coordinates[1]);

    if (
      coordinates.length !== 2 ||
      !Number.isFinite(lat) ||
      !Number.isFinite(lng) ||
      lat < -90 ||
      lat > 90 ||
      lng < -180 ||
      lng > 180
    ) {
      setError('Enter latitude and longitude separated by a comma or space.');
      return;
    }

    setError(null);
    map?.panTo({ lat, lng });
    if ((map?.getZoom() ?? 0) < 16) {
      map?.setZoom(17);
    }
    onPlaceSelected(lat, lng, '');
    setManualCoordinates('');
  };

  return (
    <div
      className={`rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-900/50 ${className}`}
    >
      <span
        id={labelId}
        className='mb-3 block text-sm font-medium text-zinc-700 dark:text-zinc-300'
      >
        Search & Add Marker
      </span>

      <div ref={containerRef} className='relative' />

      <form
        onSubmit={handleManualCoordinatesSubmit}
        className='mt-4 border-t border-zinc-200 pt-4 dark:border-zinc-700'
      >
        <p className='mb-2 text-center text-sm font-medium text-zinc-700 dark:text-zinc-300'>
          Or add coordinates
        </p>
        <div>
          <input
            type='text'
            required
            aria-label='Latitude and longitude'
            placeholder='Latitude, Longitude'
            value={manualCoordinates}
            onChange={(event) => setManualCoordinates(event.target.value)}
            className='w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 focus:outline-none dark:border-zinc-600 dark:bg-zinc-800 dark:text-white'
          />
        </div>
        <p className='mt-2 text-xs text-zinc-500 dark:text-zinc-400'>
          Example: 33.7773, -84.3963 or 33.7773 -84.3963
        </p>
      </form>

      {error ? (
        <p role='alert' className='mt-2 text-xs text-red-600 dark:text-red-400'>
          {error}
        </p>
      ) : !isReady ? (
        <p
          role='status'
          className='mt-2 text-xs text-zinc-500 dark:text-zinc-400'
        >
          {map
            ? 'Loading location search...'
            : 'Waiting for the map to load...'}
        </p>
      ) : (
        <p className='mt-2 text-xs text-zinc-500 dark:text-zinc-400'>
          Press Enter to Add Marker
        </p>
      )}
    </div>
  );
}
