'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Eye, EyeOff, KeyRound, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

type GoogleMapsApiKeyDialogProps = {
  isOpen: boolean;
  onOpenChangeAction: (_open: boolean) => void;
};

export function GoogleMapsApiKeyDialog({
  isOpen,
  onOpenChangeAction,
}: GoogleMapsApiKeyDialogProps) {
  const { toast } = useToast();
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [hasStoredKey, setHasStoredKey] = useState(false);

  const hasTypedKey = useMemo(() => apiKey.trim().length > 0, [apiKey]);

  useEffect(() => {
    if (!isOpen) return;

    const loadKey = async () => {
      setIsLoading(true);
      try {
        const response = await fetch('/api/users/maps-key', {
          method: 'GET',
          cache: 'no-store',
        });

        if (!response.ok) {
          toast({
            title: 'Could not load key',
            description: 'Please try again.',
            variant: 'destructive',
          });
          return;
        }

        const data = (await response.json()) as {
          hasKey: boolean;
          apiKey?: string;
        };

        setHasStoredKey(data.hasKey);
        setApiKey(data.apiKey ?? '');
      } catch (error) {
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };

    void loadKey();
  }, [isOpen, toast]);

  const notifyMapKeyUpdated = (nextApiKey?: string) => {
    window.dispatchEvent(
      new CustomEvent<{ apiKey?: string }>('maps-api-key-updated', {
        detail: { apiKey: nextApiKey },
      })
    );
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();

    if (!hasTypedKey) {
      toast({
        title: 'API key required',
        description: 'Please provide a Google Maps API key.',
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      const response = await fetch('/api/users/maps-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        toast({
          title: 'Save failed',
          description: data.error || 'Could not save API key.',
          variant: 'destructive',
        });
        return;
      }

      const normalizedApiKey = apiKey.trim();
      setApiKey(normalizedApiKey);
      setHasStoredKey(true);
      notifyMapKeyUpdated(normalizedApiKey);
      toast({
        title: 'API key saved',
        description: 'Your Google Maps API key was encrypted and saved.',
      });
      onOpenChangeAction(false);
    } catch (error) {
      console.error(error);
      toast({
        title: 'Save failed',
        description:
          error instanceof Error ? error.message : 'Could not save API key.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const response = await fetch('/api/users/maps-key', { method: 'DELETE' });
      if (!response.ok) {
        toast({
          title: 'Delete failed',
          description: 'Could not remove API key.',
          variant: 'destructive',
        });
        return;
      }

      setApiKey('');
      setHasStoredKey(false);
      notifyMapKeyUpdated('');
      toast({
        title: 'API key removed',
        description: 'The stored Google Maps API key has been removed.',
      });
    } catch (error) {
      console.error(error);
      toast({
        title: 'Delete failed',
        description: 'Could not remove API key.',
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
      <Dialog open={isOpen} onOpenChange={onOpenChangeAction}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <KeyRound className='h-4 w-4' />
            Google Maps API Key
          </DialogTitle>
          <DialogDescription>
            Save a personal API key for this account. The key is encrypted before
            it is stored.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSave} className='space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='google-maps-api-key'>API Key</Label>
            <div className='flex gap-2'>
              <Input
                id='google-maps-api-key'
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder='AIza...'
                autoComplete='off'
                disabled={isLoading || isSaving || isDeleting}
              />
              <Button
                type='button'
                variant='outline'
                onClick={() => setShowKey((prev) => !prev)}
                disabled={isLoading || isSaving || isDeleting}
              >
                {showKey ? (
                  <>
                    <EyeOff className='mr-2 h-4 w-4' /> Hide
                  </>
                ) : (
                  <>
                    <Eye className='mr-2 h-4 w-4' /> Show
                  </>
                )}
              </Button>
            </div>
            {hasStoredKey && (
              <p className='text-xs text-muted-foreground'>
                A key is currently stored for your account.
              </p>
            )}
          </div>

          <DialogFooter className='gap-2 sm:justify-between'>
            <Button
              type='button'
              variant='destructive'
              onClick={handleDelete}
              disabled={!hasStoredKey || isLoading || isSaving || isDeleting}
            >
              <Trash2 className='mr-2 h-4 w-4' />
              Remove Key
            </Button>
            <Button type='submit' disabled={isLoading || isSaving || isDeleting}>
              {isSaving ? 'Saving...' : 'Save Key'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}


