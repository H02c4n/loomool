import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Kiterpillar — Seller Portal",
  description: "Manage your Kiterpillar store, products, orders and payouts.",
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
              src="/brand/kiterpillar-wordmark.svg"
              alt="Kiterpillar"
              width={180}
              height={50}
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
          <p>© {new Date().getFullYear()} Kiterpillar</p>
          <p className="tagline">Make · Create · Grow</p>
        </footer>
      </body>
    </html>
  );
}
