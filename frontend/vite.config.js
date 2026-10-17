import {defineConfig} from 'vite';
export default defineConfig({base:'/ui/',build:{outDir:'../static/ui',emptyOutDir:true},server:{proxy:{'/api':'http://127.0.0.1:8501'}}});
