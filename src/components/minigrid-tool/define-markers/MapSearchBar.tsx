'use client';

import React, { useEffect, useRef } from 'react';

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
  const inputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  useEffect(() => {
    if (!map || !window.google?.maps?.places || !inputRef.current) return;

    // Cleanup previous autocomplete
    if (autocompleteRef.current) {
      google.maps.event.clearInstanceListeners(autocompleteRef.current);
    }

    const autocomplete = new google.maps.places.Autocomplete(inputRef.current, {
      fields: ['geometry', 'name', 'formatted_address'],
      types: ['geocode', 'establishment'],
    });

    autocomplete.bindTo('bounds', map);

    const handlePlaceChanged = () => {
      const place = autocomplete.getPlace();

      if (!place.geometry?.location) {
        alert("Sorry, we couldn't find location details for that place.");
        return;
      }

      const lat = place.geometry.location.lat();
      const lng = place.geometry.location.lng();
      const name =
        place.name || place.formatted_address?.split(',')[0] || 'New Location';

      // === FIXED: Safe map operations ===
      map.panTo({ lat, lng });

      // Safe zoom check
      const currentZoom = map.getZoom();
      if (currentZoom && currentZoom < 16) {
        map.setZoom(17);
      }

      // Open the Add Point Dialog
      onPlaceSelected(lat, lng, name);

      // Clear input
      if (inputRef.current) {
        inputRef.current.value = '';
      }
    };

    autocomplete.addListener('place_changed', handlePlaceChanged);

    autocompleteRef.current = autocomplete;

    // Cleanup
    return () => {
      if (autocompleteRef.current) {
        google.maps.event.clearInstanceListeners(autocompleteRef.current);
        autocompleteRef.current = null;
      }
    };
  }, [map, onPlaceSelected]);

  return (
    <div
      className={`rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-900/50 ${className}`}
    >
      <label className='mb-3 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
        Search & Add Location
      </label>

      <div className='relative'>
        <input
          ref={inputRef}
          type='text'
          placeholder={placeholder}
          className='w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 text-base placeholder:text-zinc-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 focus:outline-none dark:border-zinc-600 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500'
        />
      </div>

      <p className='mt-2 text-xs text-zinc-500 dark:text-zinc-400'>
        Search to Add Point
      </p>
    </div>
  );
}
