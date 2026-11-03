import React, { useState } from "react";
import { TrendingUp, ShoppingBag, DollarSign, ArrowUpRight, ArrowDownRight, Layers, PieChart as PieIcon, BarChart3 } from "lucide-react";

// ============================================================================
// 1. REVENUE & ORDERS INTERACTIVE AREA / BAR CHART
// ============================================================================
export interface RevenueDataPoint {
  date: string;
  label: string;
  revenue: number;
  orders: number;
}

interface RevenueChartProps {
  data?: RevenueDataPoint[];
  title?: string;
  totalRevenue?: number;
  totalOrders?: number;
}

export const RevenueTrendChart: React.FC<RevenueChartProps> = ({
  data,
  title = "Évolution du Chiffre d'Affaires & Flux des Ventes",
  totalRevenue = 0,
  totalOrders = 0,
}) => {
  const [activeRange, setActiveRange] = useState<"7d" | "30d" | "all">("7d");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Generate sensible dynamic points if data is empty (fresh store or preview)
  const defaultDays = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
  const points: RevenueDataPoint[] =
    data && data.length > 0
      ? data
      : defaultDays.map((d, i) => ({
          date: `2026-11-0${i + 1}`,
          label: d,
          revenue: totalRevenue > 0 ? Math.round((totalRevenue / 7) * (0.6 + (i * 0.15))) : 0,
          orders: totalOrders > 0 ? Math.max(1, Math.round(totalOrders / 7)) : 0,
        }));

  const maxRev = Math.max(...points.map((p) => p.revenue), 10000);
  const chartHeight = 180;
  const chartWidth = 560;
  const paddingX = 40;
  const paddingY = 25;

  const getX = (idx: number) => {
    if (points.length <= 1) return chartWidth / 2;
    return paddingX + (idx / (points.length - 1)) * (chartWidth - paddingX * 2);
  };

  const getY = (val: number) => {
    return chartHeight - paddingY - (val / maxRev) * (chartHeight - paddingY * 2);
  };

  // Build SVG path
  const pathD = points.reduce((acc, p, i) => {
    const x = getX(i);
    const y = getY(p.revenue);
    if (i === 0) return `M ${x} ${y}`;
    const prevX = getX(i - 1);
    const prevY = getY(points[i - 1].revenue);
    const cx1 = prevX + (x - prevX) / 2;
    const cx2 = cx1;
    return `${acc} C ${cx1} ${prevY}, ${cx2} ${y}, ${x} ${y}`;
  }, "");

  const areaD = `${pathD} L ${getX(points.length - 1)} ${chartHeight - paddingY} L ${getX(0)} ${chartHeight - paddingY} Z`;

  return (
    <div className="bg-white rounded-2xl border border-[#063D2E]/10 p-5 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063D2E]/10 text-[#063D2E] flex items-center justify-center font-bold">
            <BarChart3 className="w-5 h-5 text-[#063D2E]" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-sm text-[#063D2E] tracking-tight">{title}</h3>
            <p className="text-[11px] text-gray-500">Flux consolidé des transactions et volume d'expéditions</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 bg-[#F8F6F0] p-1 rounded-xl border border-[#D4AF62]/30 text-[11px]">
          {(["7d", "30d", "all"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setActiveRange(r)}
              className={`px-3 py-1 rounded-lg font-bold transition-all ${
                activeRange === r
                  ? "bg-[#063D2E] text-[#D4AF62] shadow-sm"
                  : "text-gray-500 hover:text-gray-900"
              }`}
            >
              {r === "7d" ? "7 Jours" : r === "30d" ? "30 Jours" : "Global"}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative overflow-hidden w-full">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-auto overflow-visible select-none">
          <defs>
            <linearGradient id="luxeAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#063D2E" stopOpacity="0.32" />
              <stop offset="60%" stopColor="#063D2E" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#063D2E" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="luxeStrokeGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#063D2E" />
              <stop offset="50%" stopColor="#0A5C45" />
              <stop offset="100%" stopColor="#D4AF62" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.33, 0.66, 1].map((pct, idx) => {
            const y = chartHeight - paddingY - pct * (chartHeight - paddingY * 2);
            return (
              <g key={idx}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={chartWidth - paddingX}
                  y2={y}
                  stroke="#E5E7EB"
                  strokeDasharray="4 4"
                  strokeWidth="0.75"
                />
                <text
                  x={paddingX - 6}
                  y={y + 3}
                  textAnchor="end"
                  className="text-[9px] fill-gray-400 font-mono"
                >
                  {Math.round((maxRev * pct) / 1000)}k
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          <path d={areaD} fill="url(#luxeAreaGrad)" />

          {/* Smooth Line */}
          <path d={pathD} fill="none" stroke="url(#luxeStrokeGrad)" strokeWidth="2.5" strokeLinecap="round" />

          {/* Data Points */}
          {points.map((p, idx) => {
            const x = getX(idx);
            const y = getY(p.revenue);
            const isHovered = hoveredIndex === idx;
            return (
              <g key={idx}>
                {/* Invisible hover capture area */}
                <circle
                  cx={x}
                  cy={y}
                  r="14"
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? "5.5" : "3.5"}
                  fill={isHovered ? "#D4AF62" : "#063D2E"}
                  stroke="#FFFFFF"
                  strokeWidth="2"
                  className="transition-all duration-200 pointer-events-none"
                />
                <text
                  x={x}
                  y={chartHeight - 8}
                  textAnchor="middle"
                  className={`text-[10px] font-mono transition-colors ${
                    isHovered ? "fill-[#063D2E] font-bold" : "fill-gray-400"
                  }`}
                >
                  {p.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Floating Tooltip */}
        {hoveredIndex !== null && points[hoveredIndex] && (
          <div
            className="absolute top-2 pointer-events-none transform -translate-x-1/2 bg-[#02291F] text-white px-3 py-2 rounded-xl shadow-xl border border-[#D4AF62]/40 text-xs z-20 space-y-0.5"
            style={{
              left: `${(getX(hoveredIndex) / chartWidth) * 100}%`,
            }}
          >
            <div className="text-[10px] text-[#E8D4A5] font-semibold flex items-center gap-1.5">
              <span>{points[hoveredIndex].label}</span>
              <span className="font-mono text-gray-400">({points[hoveredIndex].date})</span>
            </div>
            <div className="font-mono font-bold text-sm text-[#D4AF62]">
              {points[hoveredIndex].revenue.toLocaleString()} <span className="text-[10px] font-sans">DA</span>
            </div>
            <div className="text-[10px] text-gray-300">
              {points[hoveredIndex].orders} commande(s) enregistrée(s)
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-2 text-[11px] text-gray-500 border-t border-gray-100">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#063D2E]" />
            <span className="font-medium text-gray-700">Chiffre d'affaires brut (DZD)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#D4AF62]" />
            <span className="font-medium text-gray-700">Pic d'activité</span>
          </div>
        </div>
        <span className="font-mono text-gray-400">Mise à jour en temps réel</span>
      </div>
    </div>
  );
};

// ============================================================================
// 2. ORDER STATUS PIPELINE / DONUT CHART
// ============================================================================
interface OrderStatusDistributionProps {
  ordersByStatus: Record<string, number>;
  totalOrders: number;
}

export const OrderStatusDistributionChart: React.FC<OrderStatusDistributionProps> = ({
  ordersByStatus,
  totalOrders,
}) => {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  const statusMeta: Record<string, { label: string; color: string; desc: string }> = {
    new: { label: "Nouvelles", color: "#3B82F6", desc: "À confirmer par appel/WhatsApp" },
    confirmed: { label: "Confirmées", color: "#10B981", desc: "Validées, prêtes pour emballage" },
    preparing: { label: "En Préparation", color: "#6366F1", desc: "Colis en cours de conditionnement" },
    shipped: { label: "Expédiées", color: "#F59E0B", desc: "Prises en charge par livreur" },
    delivered: { label: "Livrées & Encaissées", color: "#063D2E", desc: "Fonds COD perçus" },
    returned: { label: "Retours COD", color: "#EF4444", desc: "Colis refusé ou injoignable" },
    cancelled: { label: "Annulées", color: "#9CA3AF", desc: "Annulées avant départ" },
  };

  const segments = Object.entries(statusMeta).map(([k, meta]) => {
    const count = ordersByStatus[k] || 0;
    const pct = totalOrders > 0 ? (count / totalOrders) * 100 : 0;
    return {
      key: k,
      count,
      pct,
      ...meta,
    };
  });

  // Calculate SVG Donut Geometry
  const size = 160;
  const strokeWidth = 22;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedPercent = 0;

  return (
    <div className="bg-white rounded-2xl border border-[#063D2E]/10 p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063D2E]/10 text-[#063D2E] flex items-center justify-center font-bold">
            <PieIcon className="w-5 h-5 text-[#063D2E]" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-sm text-[#063D2E]">Pipeline des Commandes</h3>
            <p className="text-[11px] text-gray-500">Distribution par étape opérationnelle</p>
          </div>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-[#063D2E]/10 text-[#063D2E] font-mono font-bold text-[11px]">
          {totalOrders} commande(s)
        </span>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-6 pt-2">
        {/* Donut Graphic */}
        <div className="relative w-40 h-40 shrink-0 flex items-center justify-center">
          <svg width={size} height={size} className="transform -rotate-90">
            {/* Background ring */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="#F3F4F6"
              strokeWidth={strokeWidth}
              fill="transparent"
            />
            {totalOrders > 0 ? (
              segments.map((seg) => {
                if (seg.pct <= 0) return null;
                const strokeDasharray = `${(seg.pct / 100) * circumference} ${circumference}`;
                const strokeDashoffset = -((accumulatedPercent / 100) * circumference);
                accumulatedPercent += seg.pct;

                const isHovered = hoveredKey === seg.key;
                return (
                  <circle
                    key={seg.key}
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke={seg.color}
                    strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                    strokeDasharray={strokeDasharray}
                    strokeDashoffset={strokeDashoffset}
                    fill="transparent"
                    className="transition-all duration-300 cursor-pointer"
                    onMouseEnter={() => setHoveredKey(seg.key)}
                    onMouseLeave={() => setHoveredKey(null)}
                  />
                );
              })
            ) : (
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke="#E5E7EB"
                strokeWidth={strokeWidth}
                fill="transparent"
              />
            )}
          </svg>

          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
            <span className="font-mono text-2xl font-black text-[#063D2E]">{totalOrders}</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-gray-400">Total</span>
          </div>
        </div>

        {/* Legend / Status list */}
        <div className="flex-1 w-full space-y-2">
          {segments.map((seg) => {
            const isHovered = hoveredKey === seg.key;
            return (
              <div
                key={seg.key}
                onMouseEnter={() => setHoveredKey(seg.key)}
                onMouseLeave={() => setHoveredKey(null)}
                className={`p-2 rounded-xl transition-all cursor-pointer flex items-center justify-between text-xs ${
                  isHovered ? "bg-[#F8F6F0] shadow-sm" : "hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: seg.color }}
                  />
                  <div>
                    <span className="font-bold text-gray-800">{seg.label}</span>
                    <p className="text-[10px] text-gray-400">{seg.desc}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="font-mono font-bold text-gray-900">{seg.count}</span>
                  <span className="text-[10px] font-mono text-gray-400 ml-1.5">
                    ({seg.pct.toFixed(0)}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 3. INVENTORY & STOCK VELOCITY GAUGE
// ============================================================================
interface StockGaugeProps {
  totalActive: number;
  lowStock: number;
  outOfStock: number;
  onNavigateToProducts?: () => void;
}

export const InventoryHealthWidget: React.FC<StockGaugeProps> = ({
  totalActive,
  lowStock,
  outOfStock,
  onNavigateToProducts,
}) => {
  const total = Math.max(totalActive + outOfStock, 1);
  const inStock = Math.max(0, totalActive - lowStock);
  const inStockPct = ((inStock / total) * 100).toFixed(0);
  const lowStockPct = ((lowStock / total) * 100).toFixed(0);
  const outOfStockPct = ((outOfStock / total) * 100).toFixed(0);

  return (
    <div className="bg-white rounded-2xl border border-[#063D2E]/10 p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-sm text-[#063D2E]">Santé des Stocks & Disponibilité</h3>
            <p className="text-[11px] text-gray-500">Protection anti-rupture & alertes d'approvisionnement</p>
          </div>
        </div>
        {onNavigateToProducts && (
          <button
            type="button"
            onClick={onNavigateToProducts}
            className="text-[11px] font-bold text-[#063D2E] hover:text-[#0A5C45] flex items-center gap-1 transition"
          >
            <span>Gérer</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5">
        <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden flex shadow-inner">
          <div
            style={{ width: `${inStockPct}%` }}
            className="bg-emerald-600 transition-all duration-500"
            title={`Stock Normal: ${inStockPct}%`}
          />
          <div
            style={{ width: `${lowStockPct}%` }}
            className="bg-amber-500 transition-all duration-500"
            title={`Stock Faible: ${lowStockPct}%`}
          />
          <div
            style={{ width: `${outOfStockPct}%` }}
            className="bg-red-500 transition-all duration-500"
            title={`Rupture: ${outOfStockPct}%`}
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 font-mono">
          <span>{inStockPct}% en stock optimal</span>
          <span>{(Number(lowStockPct) + Number(outOfStockPct)).toFixed(0)}% vigilance requise</span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-3 pt-1 text-center">
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">Normal</span>
          <p className="text-xl font-mono font-black text-emerald-900 mt-1">{inStock}</p>
        </div>
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800">Faible (≤3)</span>
          <p className="text-xl font-mono font-black text-amber-900 mt-1">{lowStock}</p>
        </div>
        <div className="p-3 rounded-xl bg-red-50 border border-red-200">
          <span className="text-[10px] font-bold uppercase tracking-wider text-red-800">Rupture (0)</span>
          <p className="text-xl font-mono font-black text-red-900 mt-1">{outOfStock}</p>
        </div>
      </div>
    </div>
  );
};
