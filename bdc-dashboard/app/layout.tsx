import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BDC Three-Fund Dashboard",
  description: "Dashboard for BXSL, FSK, and TSLX holdings from the centralized BDC SQLite database."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
