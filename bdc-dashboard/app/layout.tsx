import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://yardenmorad2003.github.io/bdc-three-fund-dashboard/"),
  title: "BDC Tracker | Cross-Fund Credit Research",
  description:
    "Filing-based research for eight verified BDCs, with ranked issuer signals, cross-fund loan comparisons, credit timelines, and EdgarTools coverage analysis.",
  openGraph: {
    title: "BDC Tracker | Cross-Fund Credit Research",
    description: "Reconciled BDC holdings through Q1 2026 with ranked issuer signals, audited same-loan marks, and fund-pair lead-lag tests.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og-research.png"]
  },
  twitter: {
    card: "summary_large_image",
    title: "BDC Tracker | Cross-Fund Credit Research",
    description: "Reconciled BDC holdings through Q1 2026 with ranked issuer signals, audited same-loan marks, and fund-pair lead-lag tests.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og-research.png"]
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
