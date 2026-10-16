import type { Component } from 'svelte';
import {
  BellRing,
  Bookmark,
  CalendarClock,
  FileAudio,
  LayoutDashboard,
  LayoutGrid,
  MapPin,
  Mic,
  Plane,
  Radio,
  Search,
  Smartphone,
  SquareCode,
} from '@lucide/svelte';
import Alerts from './Alerts.svelte';
import ApiDocs from './ApiDocs.svelte';
import Aprs from './Aprs.svelte';
import Bookmarks from './Bookmarks.svelte';
import Dashboard from './Dashboard.svelte';
import Decoders from './Decoders.svelte';
import Multi from './Multi.svelte';
import Pocsag from './Pocsag.svelte';
import Recordings from './Recordings.svelte';
import Repeater from './Repeater.svelte';
import Schedules from './Schedules.svelte';
import Voice from './Voice.svelte';
import Vox from './Vox.svelte';

export interface RouteDef {
  path: string;
  label: string;
  group: string;
  icon: Component<any>;
  component: Component<any>;
  usrpOnly?: boolean;
}

export const groups = ['Übersicht', 'Empfang', 'Daten', 'System'];

export const routes: RouteDef[] = [
  { path: 'dashboard', label: 'Dashboard', group: 'Übersicht', icon: LayoutDashboard, component: Dashboard },
  { path: 'voice', label: 'Sprache', group: 'Empfang', icon: Mic, component: Voice },
  { path: 'vox', label: 'VOX-Aufnahme', group: 'Empfang', icon: Radio, component: Vox },
  { path: 'aprs', label: 'APRS', group: 'Empfang', icon: MapPin, component: Aprs },
  { path: 'pocsag', label: 'POCSAG', group: 'Empfang', icon: Smartphone, component: Pocsag },
  { path: 'decoders', label: 'ADS-B · AIS · ISM', group: 'Empfang', icon: Plane, component: Decoders },
  { path: 'repeater', label: 'Repeater-Scan', group: 'Empfang', icon: Search, component: Repeater },
  {
    path: 'multi',
    label: 'Multi-Channel',
    group: 'Empfang',
    icon: LayoutGrid,
    component: Multi,
    usrpOnly: true,
  },
  { path: 'recordings', label: 'Aufnahmen', group: 'Daten', icon: FileAudio, component: Recordings },
  { path: 'bookmarks', label: 'Lesezeichen', group: 'Daten', icon: Bookmark, component: Bookmarks },
  { path: 'alerts', label: 'Alarme', group: 'Daten', icon: BellRing, component: Alerts },
  { path: 'schedules', label: 'Zeitpläne', group: 'System', icon: CalendarClock, component: Schedules },
  { path: 'api', label: 'API', group: 'System', icon: SquareCode, component: ApiDocs },
];
