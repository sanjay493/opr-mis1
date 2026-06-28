import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";

export const metadata = {
  title: "SAIL Operations Monthly Informatics (OMI) Report Portal",
  description: "Interactive report engine for viewing, editing, printing, and exporting the SAIL Operations Monthly Informatics (OMI) MIS reports.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
