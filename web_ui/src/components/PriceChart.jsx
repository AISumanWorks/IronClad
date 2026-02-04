import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import axios from 'axios';

const PriceChart = ({ ticker, strategy }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const handleResize = () => {
            if (chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
            }
        };
    }, []);

    useEffect(() => {
        if (!ticker) return;

        setLoading(true);
        setError(null);

        const fetchData = async () => {
            let marketData = [];
            let predictionData = [];

            // 1. Fetch Market Data
            try {
                const res = await axios.get(`http://localhost:8000/data/${ticker}`);
                if (res.data && res.data.data) {
                    marketData = res.data.data;
                } else {
                    throw new Error("Invalid data format received");
                }
            } catch (err) {
                console.error("Error fetching market data:", err);
                setError("Failed to load chart data. Ensure backend is running.");
                setLoading(false);
                return;
            }

            // 2. Fetch Predictions (Optional)
            try {
                const res = await axios.get(`http://localhost:8000/predictions/${ticker}`);
                predictionData = res.data.predictions || [];
            } catch (err) {
                console.warn("Could not fetch predictions:", err);
                // Continue without predictions
            }

            if (marketData.length === 0) {
                setError("No historical data available for this ticker.");
                setLoading(false);
                return;
            }

            // Render Chart
            try {
                // Clean up previous
                if (chartRef.current) {
                    chartRef.current.remove();
                }

                if (!chartContainerRef.current) return;

                const chart = createChart(chartContainerRef.current, {
                    layout: {
                        background: { type: ColorType.Solid, color: '#171717' },
                        textColor: '#a3a3a3',
                    },
                    width: chartContainerRef.current.clientWidth,
                    height: 500,
                    grid: {
                        vertLines: { color: '#262626' },
                        horzLines: { color: '#262626' },
                    },
                    timeScale: {
                        timeVisible: true,
                        secondsVisible: false,
                        borderColor: '#262626',
                    },
                    rightPriceScale: {
                        borderColor: '#262626',
                        scaleMargins: {
                            top: 0.1,
                            bottom: 0.2, // Leave space for histogram
                        },
                    }
                });

                chartRef.current = chart;

                // Candle Series
                const candleSeries = chart.addCandlestickSeries({
                    upColor: '#22c55e',
                    downColor: '#ef4444',
                    borderVisible: false,
                    wickUpColor: '#22c55e',
                    wickDownColor: '#ef4444',
                });

                // Sort data by time to be safe
                marketData.sort((a, b) => a.time - b.time);

                // Deduplicate times (lightweight-charts crashes on duplicates)
                const uniqueData = [];
                const seenTimes = new Set();
                for (const d of marketData) {
                    if (d.time && !seenTimes.has(d.time)) {
                        seenTimes.add(d.time);
                        // Ensure required fields
                        if (d.open != null && d.close != null && d.high != null && d.low != null) {
                            uniqueData.push({
                                time: d.time,
                                open: d.open,
                                high: d.high,
                                low: d.low,
                                close: d.close
                            });
                        }
                    }
                }

                if (uniqueData.length === 0) {
                    setError("Data invalid or empty.");
                    setLoading(false);
                    return;
                }

                candleSeries.setData(uniqueData);

                // Indicators
                const sma50Data = marketData
                    .filter(d => d.sma_50 && !isNaN(d.sma_50))
                    .map(d => ({ time: d.time, value: d.sma_50 }));

                if (sma50Data.length > 0) {
                    const sma50Series = chart.addLineSeries({
                        color: '#3b82f6',
                        lineWidth: 2,
                        priceLineVisible: false,
                    });
                    sma50Series.setData(sma50Data);
                }

                // AI Predictions Overlay
                // Only plot if we have predictions
                if (predictionData.length > 0) {
                    // Try to match predictions to chart times
                    // Or just plot them as points ?
                    // Let's rely on time closeness?

                    // For now, let's keep it simple: Markers
                    const recentPredictions = predictionData.slice(0, 50); // Last 50
                    const markers = [];

                    recentPredictions.forEach(pred => {
                        const pTime = new Date(pred.timestamp).getTime() / 1000;
                        // Find closest candle time
                        // This is O(N*M), slow? No, N=50.
                        // Find exact match or closest
                        // For simplicity, find exact match in uniqueData
                        // Round to nearest 5 mins (300s)
                        const roundedTime = Math.round(pTime / 300) * 300;

                        // Check if exists in existing data?
                        // If not, marker won't show.

                        // Simply iterate data to find match
                        // Or use the time directly if it matches candle time logic

                        if (seenTimes.has(roundedTime)) {
                            markers.push({
                                time: roundedTime,
                                position: 'aboveBar',
                                color: '#eab308',
                                shape: 'circle',
                                text: `AI: ${(pred.confidence * 100).toFixed(0)}%`
                            });
                        }
                    });

                    if (markers.length > 0) {
                        // candleSeries.setMarkers(markers);
                    }
                }

                chart.timeScale().fitContent();
            } catch (renderErr) {
                console.error("Error rendering chart:", renderErr);
                setError("Error rendering chart: " + renderErr.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();

    }, [ticker, strategy]);

    return (
        <div className="relative w-full h-full">
            {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-neutral-900/50 z-10">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div>
                </div>
            )}

            {error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900 z-0">
                    <p className="text-red-500 mb-2">⚠ {error}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="text-xs bg-neutral-800 px-3 py-1 rounded hover:bg-neutral-700 text-white"
                    >
                        Retry
                    </button>
                </div>
            )}

            <div ref={chartContainerRef} className="w-full h-full" />
        </div>
    );
};

export default PriceChart;
