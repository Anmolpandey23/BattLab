import type { Metadata } from "next";
import { ConsoleSuppressionInit } from "@/components/ConsoleSuppressionInit";
import "./globals.css";

export const metadata: Metadata = {
  title: "BattLab — Virtual Battery Pack Design & Simulation Platform",
  description:
    "High-precision 3D battery pack engineering and simulation platform. Design topologies, inspect exploded CAD assemblies, and simulate multi-physics electro-thermal dynamics.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-32x32.png", type: "image/png", sizes: "32x32" },
      { url: "/favicon-16x16.png", type: "image/png", sizes: "16x16" },
      { url: "/icon-512.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ backgroundColor: "#030712", colorScheme: "dark" }}>
      <body style={{ backgroundColor: "#030712", color: "#f8fafc", margin: 0, minHeight: "100vh" }}>
        <ConsoleSuppressionInit />
        {children}
      </body>
    </html>
  );
}
