import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://yardenmorad2003.github.io/bdc-three-fund-dashboard/"),
  title: "BDC Tracker | Portfolio Overview",
  description:
    "Filing-based portfolio research for eight verified BDCs, with holdings, credit, financial, and EdgarTools coverage analysis.",
  openGraph: {
    title: "BDC Tracker | Portfolio Overview",
    description: "Reconciled BDC holdings through Q1 2026 with credit analytics and an audited EdgarTools expansion cohort.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og.png"]
  },
  twitter: {
    card: "summary_large_image",
    title: "BDC Tracker | Portfolio Overview",
    description: "Reconciled BDC holdings through Q1 2026 with credit analytics and an audited EdgarTools expansion cohort.",
    images: ["https://yardenmorad2003.github.io/bdc-three-fund-dashboard/og.png"]
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
