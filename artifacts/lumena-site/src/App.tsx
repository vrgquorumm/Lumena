import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import Home from '@/pages/home';
import GamePage from '@/pages/game';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp';

const queryClient = new QueryClient();

function Router() {
  return (
    <Switch>
      <Route path="/" component={Home} />
      <Route path="/game" component={GamePage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  // Ініціалізуємо Telegram Mini App SDK (викликає ready() + expand())
  useTelegramWebApp();

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
