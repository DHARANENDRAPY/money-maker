import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';

export default function CandlestickChart({
  candles = [],
  keyLevels = null,
  signal = null,
  activeTrade = null,
  height = 420,
  showVolume = true,
  showVwap = true,
  showEma = true
}) {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#090d16' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#0284c7',
          width: 1,
          style: 3,
        },
        horzLine: {
          color: '#0284c7',
          width: 1,
          style: 3,
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        scaleMargins: {
          top: 0.1,
          bottom: showVolume ? 0.25 : 0.1,
        },
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
      height: height,
    });

    chartInstanceRef.current = chart;

    // 1. Candlestick Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // 2. Volume Series
    let volumeSeries = null;
    if (showVolume) {
      volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '', // overlay
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
    }

    // 3. VWAP Line
    let vwapSeries = null;
    if (showVwap) {
      vwapSeries = chart.addLineSeries({
        color: '#38bdf8',
        lineWidth: 2,
        title: 'VWAP',
      });
    }

    // 4. EMA 9 & EMA 21 Lines
    let ema9Series = null;
    let ema21Series = null;
    if (showEma) {
      ema9Series = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 1,
        title: 'EMA 9',
      });
      ema21Series = chart.addLineSeries({
        color: '#a855f7',
        lineWidth: 1,
        title: 'EMA 21',
      });
    }

    // Format candle data
    if (candles && candles.length > 0) {
      const formattedCandles = [];
      const formattedVolumes = [];
      const formattedVwap = [];
      const formattedEma9 = [];
      const formattedEma21 = [];

      candles.forEach((c) => {
        // Parse time to unix timestamp in seconds
        const timeSec = Math.floor(new Date(c.timestamp).getTime() / 1000);
        if (isNaN(timeSec)) return;

        formattedCandles.push({
          time: timeSec,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        });

        if (showVolume && c.volume !== undefined) {
          formattedVolumes.push({
            time: timeSec,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)',
          });
        }

        if (showVwap && c.vwap !== null && c.vwap !== undefined) {
          formattedVwap.push({ time: timeSec, value: c.vwap });
        }
        if (showEma && c.ema9 !== null && c.ema9 !== undefined) {
          formattedEma9.push({ time: timeSec, value: c.ema9 });
        }
        if (showEma && c.ema21 !== null && c.ema21 !== undefined) {
          formattedEma21.push({ time: timeSec, value: c.ema21 });
        }
      });

      // Sort by time ascending
      formattedCandles.sort((a, b) => a.time - b.time);
      formattedVolumes.sort((a, b) => a.time - b.time);
      formattedVwap.sort((a, b) => a.time - b.time);
      formattedEma9.sort((a, b) => a.time - b.time);
      formattedEma21.sort((a, b) => a.time - b.time);

      candleSeries.setData(formattedCandles);
      if (volumeSeries && formattedVolumes.length > 0) volumeSeries.setData(formattedVolumes);
      if (vwapSeries && formattedVwap.length > 0) vwapSeries.setData(formattedVwap);
      if (ema9Series && formattedEma9.length > 0) ema9Series.setData(formattedEma9);
      if (ema21Series && formattedEma21.length > 0) ema21Series.setData(formattedEma21);

      // Support & Resistance Price Lines
      if (keyLevels) {
        if (keyLevels.resistance_1) {
          candleSeries.createPriceLine({
            price: keyLevels.resistance_1,
            color: 'rgba(239, 68, 68, 0.7)',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'R1',
          });
        }
        if (keyLevels.support_1) {
          candleSeries.createPriceLine({
            price: keyLevels.support_1,
            color: 'rgba(16, 185, 129, 0.7)',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'S1',
          });
        }
        if (keyLevels.orb_high) {
          candleSeries.createPriceLine({
            price: keyLevels.orb_high,
            color: 'rgba(56, 189, 248, 0.6)',
            lineWidth: 1,
            lineStyle: 1,
            axisLabelVisible: true,
            title: 'ORH (15m)',
          });
        }
      }

      // 1. Active Paper Trade Position Overlays (Real-time live position lines)
      if (activeTrade) {
        const entry = Number(activeTrade.entry_price);
        const t1 = Number(activeTrade.target_1);
        const t2 = Number(activeTrade.target_2 || (t1 * 1.02));
        const sl = Number(activeTrade.stop_loss);
        const trailing = activeTrade.trailing_status;
        const shares = activeTrade.shares || 1;

        if (entry) {
          candleSeries.createPriceLine({
            price: entry,
            color: '#38bdf8',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: `ENTRY: ₹${entry.toFixed(2)} (${shares} sh)`,
          });
        }

        if (t1) {
          candleSeries.createPriceLine({
            price: t1,
            color: '#10b981',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: activeTrade.t1_booked ? `T1: ₹${t1.toFixed(2)} (BOOKED ✓)` : `T1: ₹${t1.toFixed(2)} (50% BOOK)`,
          });
        }

        if (t2) {
          candleSeries.createPriceLine({
            price: t2,
            color: '#f59e0b',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `T2 RUNNER: ₹${t2.toFixed(2)}`,
          });
        }

        if (sl) {
          let slTitle = `STOP LOSS: ₹${sl.toFixed(2)}`;
          let slColor = '#ef4444';

          if (trailing === 'PROFIT_LOCKED_35PCT') {
            slTitle = `🛡️ 35% PROFIT LOCKED: ₹${sl.toFixed(2)}`;
            slColor = '#06b6d4';
          } else if (trailing === 'RISK_FREE_BREAKEVEN') {
            slTitle = `🔒 ZERO RISK (BE): ₹${sl.toFixed(2)}`;
            slColor = '#10b981';
          } else if (trailing === 'T1_BOOKED_RUNNER_ACTIVE') {
            slTitle = `🏃 RUNNER SL (BE): ₹${sl.toFixed(2)}`;
            slColor = '#10b981';
          } else if (trailing === 'RUNNER_PROFIT_LOCKED_T1') {
            slTitle = `🏆 RUNNER SL (@ T1): ₹${sl.toFixed(2)}`;
            slColor = '#10b981';
          }

          candleSeries.createPriceLine({
            price: sl,
            color: slColor,
            lineWidth: 2,
            lineStyle: trailing ? 0 : 2,
            axisLabelVisible: true,
            title: slTitle,
          });
        }
      }
      // 2. Setup / Signal Target & Stop Loss price lines (if no active trade is open)
      else if (signal) {
        const t1 = signal.target_1 || signal.target_price;
        const t2 = signal.target_2;
        if (t1) {
          candleSeries.createPriceLine({
            price: Number(t1),
            color: '#10b981',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: 'Target 1 (TP1)',
          });
        }
        if (t2) {
          candleSeries.createPriceLine({
            price: Number(t2),
            color: '#06b6d4',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'Target 2 (Runner)',
          });
        }
        if (signal.stop_loss) {
          candleSeries.createPriceLine({
            price: Number(signal.stop_loss),
            color: '#ef4444',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: 'Stop Loss (SL)',
          });
        }
        if (signal.entry_price) {
          candleSeries.createPriceLine({
            price: Number(signal.entry_price),
            color: '#38bdf8',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'Entry Trigger',
          });
        }
      }

      chart.timeScale().fitContent();
    }

    // Responsive Resize Observer
    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
    };
  }, [candles, keyLevels, signal, activeTrade, height, showVolume, showVwap, showEma]);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-slate-800/80 bg-slate-950/60 shadow-lg">
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
      {(!candles || candles.length === 0) && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 text-xs text-slate-500">
          Loading candle chart data...
        </div>
      )}
    </div>
  );
}
