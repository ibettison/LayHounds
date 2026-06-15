import React from "react";
import { Activity, ArrowLeft, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { LicencePanel } from "../components/LicencePanel";
import { Button } from "../components/ui/button";


export default function Licence() {
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white">
      <header className="border-b border-[#2A2A2A]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-pink-600 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-display text-2xl font-black uppercase tracking-tighter">Lay-Hounds</div>
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">Licence management</div>
            </div>
          </Link>
          <Link to="/">
            <Button
              variant="outline"
              className="rounded-none border-[#2A2A2A] bg-transparent text-zinc-300 hover:bg-[#141414] hover:text-white"
            >
              <ArrowLeft className="w-4 h-4 mr-2" /> App
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        <div className="mb-5">
          <div className="flex items-center gap-2 text-pink-400">
            <KeyRound className="w-5 h-5" />
            <span className="text-xs font-mono uppercase tracking-widest">Live Unlock</span>
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-black uppercase tracking-tight mt-2">
            Manage your licence
          </h1>
          <p className="text-zinc-400 mt-2">
            Activate a licence key, check its status, refresh validation or release this install.
          </p>
        </div>
        <LicencePanel />
      </main>
    </div>
  );
}
