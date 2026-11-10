import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Loomool — Seller Portal",
  description: "Manage your Loomool store, products, orders and payouts.",
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
            <Link href="/">Dashboard</Link>
            <Link href="/products">Products</Link>
            <Link href="/orders">Orders</Link>
            <Link href="/payouts">Payouts</Link>
          </nav>
        </header>
        <main className="site-main">{children}</main>
        <footer className="site-footer">
          <p>© {new Date().getFullYear()} Loomool</p>
          <p className="tagline">Sell it with Loomool</p>
        </footer>
      </body>
    </html>
  );
}