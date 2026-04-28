import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { RequireAuth } from './components/auth/RequireAuth';
import { RequireAdmin } from './components/auth/RequireAdmin';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { ModelsPage } from './features/models/ModelsPage';
import { JudgesPage } from './features/judges/JudgesPage';
import { TasksPage } from './features/tasks/TasksPage';
import { BatchesPage } from './features/batches/BatchesPage';
import { BatchDetailPage } from './features/batches/BatchDetailPage';
import { JobsPage } from './features/jobs/JobsPage';
import { UsersPage } from './features/users/UsersPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'models', element: <ModelsPage /> },
      { path: 'judges', element: <JudgesPage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'batches', element: <BatchesPage /> },
      { path: 'batches/:id', element: <BatchDetailPage /> },
      { path: 'jobs', element: <JobsPage /> },
      {
        path: 'users',
        element: (
          <RequireAdmin>
            <UsersPage />
          </RequireAdmin>
        ),
      },
      { path: 'settings', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
