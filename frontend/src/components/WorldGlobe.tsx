import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import { MeshPhongMaterial } from "three";
import { feature } from "topojson-client";
import type { Feature, Geometry } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import countriesTopo from "world-atlas/countries-110m.json";
import type { WorldMarket, WorldPeriod } from "../api/client";
import type { Theme } from "../theme";
import { changeColor, palette } from "../utils/worldColors";
import { formatPercent } from "../utils/format";

type Country = Feature<Geometry, { name: string }>;

const topo = countriesTopo as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>;
const COUNTRIES = feature(topo, topo.objects.countries).features as Country[];
const POLYGON_IDS = new Set(COUNTRIES.map((c) => String(c.id)));

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);
}

function tooltip(name: string, market: WorldMarket | undefined, period: WorldPeriod): string {
  if (!market) return `<b>${escapeHtml(name)}</b><br/>No market tracked`;
  const change = market[period];
  return (
    `<b>${escapeHtml(market.country)}</b><br/>` +
    `${escapeHtml(market.index_name)}${market.kind === "etf" ? " (ETF)" : ""}<br/>` +
    (change === null ? "No data" : `<b>${formatPercent(change)}</b>`)
  );
}

interface Props {
  markets: WorldMarket[];
  period: WorldPeriod;
  theme: Theme;
  selectedIso: string | null;
  onSelect: (iso: string | null) => void;
}

export function WorldGlobe({ markets, period, theme, selectedIso, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hoverIso, setHoverIso] = useState<string | null>(null);
  const dark = theme === "dark";
  const colors = palette(dark);

  const byIso = useMemo(() => new Map(markets.map((m) => [m.iso_n3, m])), [markets]);
  // Markets too small to have a polygon at this map resolution (Hong Kong, Singapore).
  const points = useMemo(() => markets.filter((m) => !POLYGON_IDS.has(m.iso_n3)), [markets]);

  const oceanMaterial = useMemo(() => new MeshPhongMaterial({ color: colors.ocean }), [colors.ocean]);
  useEffect(() => () => oceanMaterial.dispose(), [oceanMaterial]);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Measure now so the globe can render on first paint; the observer handles later resizes.
    const { width, height } = el.getBoundingClientRect();
    setSize({ width, height });
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Spin slowly until the user is looking at something.
  useEffect(() => {
    const controls = globeRef.current?.controls();
    if (controls) controls.autoRotate = !hoverIso && !selectedIso;
  }, [hoverIso, selectedIso]);

  useEffect(() => {
    const market = selectedIso ? byIso.get(selectedIso) : undefined;
    if (market) globeRef.current?.pointOfView({ lat: market.lat, lng: market.lng, altitude: 1.8 }, 1000);
  }, [selectedIso, byIso]);

  function handleReady() {
    const globe = globeRef.current;
    if (!globe) return;
    globe.pointOfView({ lat: 25, lng: 100, altitude: 1.7 });
    const controls = globe.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;
  }

  const idOf = (obj: object) => String((obj as Country).id);

  return (
    <div ref={containerRef} className="h-[520px] w-full cursor-grab active:cursor-grabbing">
      {size.width > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeMaterial={oceanMaterial}
          atmosphereColor={colors.atmosphere}
          atmosphereAltitude={0.15}
          onGlobeReady={handleReady}
          polygonsData={COUNTRIES}
          polygonCapColor={(obj) => {
            const market = byIso.get(idOf(obj));
            return market ? changeColor(market[period], period, dark) : colors.untracked;
          }}
          polygonSideColor={() => colors.side}
          polygonStrokeColor={() => colors.stroke}
          polygonAltitude={(obj) => {
            const id = idOf(obj);
            if (id === selectedIso) return 0.05;
            return id === hoverIso && byIso.has(id) ? 0.025 : 0.008;
          }}
          polygonsTransitionDuration={250}
          polygonLabel={(obj) => tooltip((obj as Country).properties.name, byIso.get(idOf(obj)), period)}
          onPolygonHover={(obj) => setHoverIso(obj ? idOf(obj) : null)}
          onPolygonClick={(obj) => {
            const id = idOf(obj);
            onSelect(byIso.has(id) ? id : null);
          }}
          pointsData={points}
          pointLat="lat"
          pointLng="lng"
          pointColor={(obj) => changeColor((obj as WorldMarket)[period], period, dark)}
          pointAltitude={(obj) => ((obj as WorldMarket).iso_n3 === selectedIso ? 0.08 : 0.03)}
          pointRadius={1.1}
          pointLabel={(obj) => tooltip((obj as WorldMarket).country, obj as WorldMarket, period)}
          onPointHover={(obj) => setHoverIso(obj ? (obj as WorldMarket).iso_n3 : null)}
          onPointClick={(obj) => onSelect((obj as WorldMarket).iso_n3)}
        />
      )}
    </div>
  );
}
