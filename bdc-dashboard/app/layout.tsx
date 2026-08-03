import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://yardenmorad2003.github.io/bdc-three-fund-dashboard/"),
  title: "BDC Tracker | Cross-Fund Credit Research",
  description:
    "Filing-based research for sixteen verified BDCs, with SEC bond issuance, FINRA TRACE trading, cross-fund loan comparisons, and credit timelines.",
  openGraph: {
    title: "BDC Tracker | Cross-Fund Credit Research",
    description: "SEC note issuance and FINRA TRACE trading alongside reconciled holdings, cross-fund marks, and credit timelines.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og-funding.png"]
  },
  twitter: {
    card: "summary_large_image",
    title: "BDC Tracker | Cross-Fund Credit Research",
    description: "SEC note issuance and FINRA TRACE trading alongside reconciled holdings, cross-fund marks, and credit timelines.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og-funding.png"]
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
