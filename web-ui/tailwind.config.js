/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Zero Trust brand colors
                'zt-primary': '#2563eb',
                'zt-secondary': '#1e40af',
                'zt-success': '#10b981',
                'zt-warning': '#f59e0b',
                'zt-danger': '#ef4444',
                'zt-dark': '#0f172a',
                'zt-darker': '#020617',
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'spin-slow': 'spin 3s linear infinite',
            },
        },
    },
    plugins: [],
}
