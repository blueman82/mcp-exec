import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Ketchup Log Viewer',
  description: 'Multi-server Docker container log monitoring with Okta 2FA SSH authentication',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
