export function WorldMap({ svg, dark = true, className = "" }: { svg: string; dark?: boolean; className?: string }) {
  return <div className={`mapbox ${dark ? "dark" : ""} ${className}`} dangerouslySetInnerHTML={{ __html: svg }} />;
}
