import { Fraunces } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["500", "600"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

export const metadata = {
  title: "Office Hours — learn from any video",
  description: "Paste a YouTube link and get tutored or quizzed on it.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={fraunces.variable}>
      <body>
        <div className="app-shell">
          <header className="app-header">
            <span className="logo">Office Hours</span>
            <span className="tagline">learn from any video</span>
          </header>
          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
