import { createContext } from 'react';

interface LayoutHeaderContextValue {
  openMobileMenu: () => void;
  registerPageHeader: () => void;
  unregisterPageHeader: () => void;
  showMobileMenuButton: boolean;
}

export const LayoutHeaderContext = createContext<LayoutHeaderContextValue | null>(null);
