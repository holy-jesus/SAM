import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

import SetupView from '@/views/SetupView.vue';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import ComplianceView from '@/views/ComplianceView.vue';
import EmployeesView from '@/views/EmployeesView.vue';
import ComputersView from '@/views/ComputersView.vue';
import InstalledSoftwareView from '@/views/InstalledSoftwareView.vue';
import SoftwareCatalogView from '@/views/SoftwareCatalogView.vue';
import LicensesView from '@/views/LicensesView.vue';
import CategoriesView from '@/views/CategoriesView.vue';
import ClassifiersView from '@/views/ClassifiersView.vue';
import RegistryView from '@/views/RegistryView.vue';
import ImportDumpView from '@/views/ImportDumpView.vue';
import AIChatView from '@/views/AIChatView.vue';

const routes: RouteRecordRaw[] = [
  {
    path: '/setup',
    name: 'setup',
    component: SetupView,
    meta: { public: true },
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: DashboardView,
  },
  {
    path: '/compliance',
    name: 'compliance',
    component: ComplianceView,
  },
  {
    path: '/employees',
    name: 'employees',
    component: EmployeesView,
  },
  {
    path: '/computers',
    name: 'computers',
    component: ComputersView,
  },
  {
    path: '/installed-software',
    name: 'installed-software',
    component: InstalledSoftwareView,
  },
  {
    path: '/catalog',
    name: 'catalog',
    component: SoftwareCatalogView,
  },
  {
    path: '/licenses',
    name: 'licenses',
    component: LicensesView,
  },
  {
    path: '/categories',
    name: 'categories',
    component: CategoriesView,
  },
  {
    path: '/classifiers',
    name: 'classifiers',
    component: ClassifiersView,
  },
  {
    path: '/registry',
    name: 'registry',
    component: RegistryView,
  },
  {
    path: '/import',
    name: 'import',
    component: ImportDumpView,
  },
  {
    path: '/ai-chat',
    name: 'ai-chat',
    component: AIChatView,
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // Check initial setup status if not yet checked
  if (authStore.isInitialized === null) {
    await authStore.checkSetup();
  }

  // If service is not initialized, force redirect to /setup
  if (!authStore.isInitialized && to.path !== '/setup') {
    return next('/setup');
  }

  // If service is initialized and user is going to /setup, redirect to /login or /dashboard
  if (authStore.isInitialized && to.path === '/setup') {
    return next('/login');
  }

  // Public routes (login)
  if (to.meta.public) {
    if (authStore.isAuthenticated && to.path === '/login') {
      return next('/dashboard');
    }
    return next();
  }

  // Protected routes: check if authenticated
  if (!authStore.isAuthenticated) {
    return next('/login');
  }

  next();
});
