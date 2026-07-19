import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";
import { AuthProvider } from "@/providers/AuthProvider";

export const metadata = {
  title: "SAIL Operations Monthly Informatics (OMI) Report Portal",
  description: "Interactive report engine for viewing, editing, printing, and exporting the SAIL Operations Monthly Informatics (OMI) MIS reports.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
