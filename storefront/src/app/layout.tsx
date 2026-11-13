import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Loomool — Make it. Kit it. Sell it.",
  description:
    "Marketplace for DIY kits, handmade goods, materials and creative workshops.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            <Image
              src="/brand/loomool-wordmark.svg"
              alt="Loomool"
              width={200}
              height={56}
              priority
            />
          </Link>
          <nav className="site-nav">
            <Link href="/">Shop</Link>
            <Link href="/sellers">Sellers</Link>
            <Link href="/about">About</Link>
          </nav>
        </header>
        <main className="site-main">{children}</main>
        <footer className="site-footer">
          <p>© {new Date().getFullYear()} Loomool</p>
          <p className="tagline">Make it · Kit it · Sell it</p>
        </footer>
      </body>
    </html>
  );
}
