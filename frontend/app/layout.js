export const metadata = {
  title: "Member Callout",
  description: "Leadership screen for sending and tracking a callout announcement.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          margin: "2rem",
          color: "#111",
          background: "#fff",
          colorScheme: "light",
        }}
      >
        {children}
      </body>
    </html>
  );
}
