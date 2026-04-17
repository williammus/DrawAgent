import type { PropsWithChildren } from "react";
import { Toaster } from "sonner";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <>
      {children}
      <Toaster
        position="top-center"
        richColors
        theme="dark"
        toastOptions={{
          classNames: {
            toast: "!border-white/10 !bg-[#161819] !text-slate-100",
          },
        }}
      />
    </>
  );
}
