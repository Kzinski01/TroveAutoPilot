import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'Trove AutoBot',
  description: 'Auto clique, skills, poção e janelas para o Trove',
  icons: { icon: '/icon.ico' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="dark">
      <body>{children}</body>
    </html>
  );
}
