import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import Showcase from './Showcase';
import CookieApp from './CookieApp';
import './style.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode>{import.meta.env.VITE_SHOWCASE_MODE === 'true' ? <Showcase/> : import.meta.env.VITE_COOKIE_AUTH_MODE === 'true' ? <CookieApp/> : <App/>}</React.StrictMode>);
