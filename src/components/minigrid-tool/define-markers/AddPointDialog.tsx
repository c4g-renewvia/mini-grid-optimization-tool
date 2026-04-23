'use client';

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface AddPointDialogProps {
  isOpen: boolean;
  onOpenChange: (_open: boolean) => void;
  newPointDetails: { name: string; type: 'source' | 'terminal' | 'pole' };
  onNewPointDetailsChange: (_details: {
    name: string;
    type: 'source' | 'terminal' | 'pole';
  }) => void;
  onConfirm: () => void;
}

export default function AddPointDialog({
  isOpen,
  onOpenChange,
  newPointDetails,
  onNewPointDetailsChange,
  onConfirm,
}: AddPointDialogProps) {
  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onConfirm();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className='border-zinc-200 bg-white text-zinc-900 sm:max-w-106.25 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white'>
        <DialogHeader>
          <DialogTitle className='text-zinc-900 dark:text-white'>
            Add New Point
          </DialogTitle>
          <DialogDescription className='text-zinc-500 dark:text-zinc-400'>
            Set the details for the location you just clicked.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className='grid gap-4 py-4'>
            <div className='grid grid-cols-4 items-center gap-4'>
              <label
                htmlFor='new-point-name'
                className='text-right text-sm text-zinc-700 dark:text-zinc-300'
              >
                Name
              </label>
              <input
                id='new-point-name'
                value={newPointDetails.name}
                onChange={(e) =>
                  onNewPointDetailsChange({
                    ...newPointDetails,
                    name: e.target.value,
                  })
                }
                className='col-span-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:focus:border-emerald-500'
              />
            </div>
            <div className='grid grid-cols-4 items-center gap-4'>
              <label
                htmlFor='new-point-type'
                className='text-right text-sm text-zinc-700 dark:text-zinc-300'
              >
                Type
              </label>
              <select
                id='new-point-type'
                value={newPointDetails.type}
                onChange={(e) =>
                  onNewPointDetailsChange({
                    ...newPointDetails,
                    type: e.target.value as 'source' | 'terminal' | 'pole',
                  })
                }
                className='col-span-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:focus:border-emerald-500'
              >
                <option value='terminal'>Terminal</option>
                <option value='source'>Source</option>
                <option value='pole'>Pole</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <button
              type='button'
              onClick={() => onOpenChange(false)}
              className='px-4 py-2 text-sm font-medium text-zinc-500 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white'
            >
              Cancel
            </button>
            <button
              type='submit'
              className='rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 active:bg-emerald-700'
            >
              Add Point
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
