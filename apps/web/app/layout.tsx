import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GoreeCloud Search",
  description: "An independent public web search project.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="gc-app">{children}</body>
    </html>
  );
}
