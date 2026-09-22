export default function AtlasLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#000",
        zIndex: 100,
      }}
    >
      {children}
    </div>
  );
}
