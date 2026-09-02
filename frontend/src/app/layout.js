import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";
import { AuthProvider } from "@/providers/AuthProvider";
import VisitLogger from "@/components/VisitLogger";

export const metadata = {
  title: "SAIL Operations Monthly Informatics (OMI) Report Portal",
  description: "Interactive report engine for viewing, editing, printing, and exporting the SAIL Operations Monthly Informatics (OMI) MIS reports.",
};

export default function RootLayout({ children }) {
  return (
    // suppressHydrationWarning: browser extensions (Quillbot adds
    // data-qb-installed, Grammarly, dark-mode toggles, …) mutate <html>/<body>
    // before React hydrates, which otherwise logs a hydration-mismatch error.
    // This only silences the warning on these two elements, not on app content.
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <QueryProvider>
          <AuthProvider>
            <VisitLogger />
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
