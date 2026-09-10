import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "VariantRAG · Evidence workbench",
  description:
    "Inspect variant evidence, case tables, and auditable comparisons.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
