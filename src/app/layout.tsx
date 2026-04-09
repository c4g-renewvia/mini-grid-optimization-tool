import { ImpersonationProvider } from '@/components/contexts/impersonation-context';
import { Footer } from '@/components/layout/footer';
import { ServiceWorkerRegistration } from '@/components/layout/service-worker-registration';
import { ThemeProvider } from '@/components/layout/theme-provider';
import { Toaster } from '@/components/ui/toaster';
import { auth } from '@/lib/auth';
import type { Metadata, Viewport } from 'next';
import { SessionProvider } from 'next-auth/react';
import localFont from 'next/font/local';
import './globals.css';

import { SpeedInsights } from '@vercel/speed-insights/next';
import { Analytics } from '@vercel/analytics/next';

const geistSans = localFont({
  src: './fonts/GeistVF.woff',
  variable: '--font-geist-sans',
  weight: '100 900',
});
const geistMono = localFont({
  src: './fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
  weight: '100 900',
});

export const metadata: Metadata = {
  title: 'Mini-Grid Optimizer',
  description:
    'Computing for Good - Renewvia Project',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Mini-Grid Optimization Tool',
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: '/lightning.png', sizes: '16x16', type: 'image/png' },
      { url: '/lightning.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#000000',
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await auth();
  return (
    <html lang='en' suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider attribute='class' defaultTheme='system' enableSystem>
          <SessionProvider session={session}>
            <ImpersonationProvider>
              <ServiceWorkerRegistration />
              <div className='mt-16 min-h-[calc(100dvh-8.4rem)]'>
                {children}
                <SpeedInsights />
                <Analytics />
              </div>
              <Footer />
              <Toaster />
            </ImpersonationProvider>
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
