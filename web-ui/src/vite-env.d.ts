/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL: string
    readonly VITE_ADMIN_TOKEN: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}

declare module '*.css' {
    const content: { [className: string]: string }
    export default content
}
