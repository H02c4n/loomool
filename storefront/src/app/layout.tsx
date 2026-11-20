import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import CartBadge from "@/components/CartBadge";

import "./globals.css";

export const metadata: Metadata = {
  title: "kiterpillar — Make it. Kit it. Sell it.",
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
              src="/brand/kiterpillar-wordmark.svg"
              alt="kiterpillar"
              width={160}
              height={45}
              priority
            />
          </Link>
          <nav className="site-nav">
            <Link href="/search">Shop</Link>
            <Link href="/favorites">Favorites</Link>
            <Link href="/orders">Orders</Link>
            <Link href="/cart" className="site-nav__cart">
              Cart <CartBadge />
            </Link>
            <Link href="/login">Login</Link>
            <Link href="/register" className="site-nav__cta">
              Sign up
            </Link>
          </nav>
        </header>
        <main className="site-main">{children}</main>
        <footer className="site-footer">
          <p>© {new Date().getFullYear()} kiterpillar</p>
          <p className="tagline">Make it · Kit it · Sell it</p>
        </footer>
      </body>
    </html>
  );
}
