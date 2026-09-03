import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useSeo } from '../seo';
import { seoForPath } from '../seoRoutes';

export default function RouteSeoManager() {
  const location = useLocation();
  const { user } = useAuth();

  useSeo(seoForPath(location.pathname, { search: location.search, isAuthenticated: Boolean(user) }));

  return null;
}
