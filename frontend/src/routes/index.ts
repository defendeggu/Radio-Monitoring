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
import { t } from '../lib/i18n.svelte';

export interface RouteDef {
  path: string;
  label: () => string;
  group: GroupId;
  icon: Component<any>;
  component: Component<any>;
  usrpOnly?: boolean;
}

export type GroupId = 'overview' | 'receive' | 'data' | 'system';

export const groups: { id: GroupId; label: () => string }[] = [
  { id: 'overview', label: () => t('Übersicht') },
  { id: 'receive', label: () => t('Empfang') },
  { id: 'data', label: () => t('Daten') },
  { id: 'system', label: () => t('System') },
];

export const routes: RouteDef[] = [
  {
    path: 'dashboard',
    label: () => t('Dashboard'),
    group: 'overview',
    icon: LayoutDashboard,
    component: Dashboard,
  },
  { path: 'voice', label: () => t('Sprache'), group: 'receive', icon: Mic, component: Voice },
  { path: 'vox', label: () => t('VOX-Aufnahme'), group: 'receive', icon: Radio, component: Vox },
  { path: 'aprs', label: () => 'APRS', group: 'receive', icon: MapPin, component: Aprs },
  { path: 'pocsag', label: () => 'POCSAG', group: 'receive', icon: Smartphone, component: Pocsag },
  { path: 'decoders', label: () => 'ADS-B · AIS · ISM', group: 'receive', icon: Plane, component: Decoders },
  { path: 'repeater', label: () => t('Repeater-Scan'), group: 'receive', icon: Search, component: Repeater },
  {
    path: 'multi',
    label: () => 'Multi-Channel',
    group: 'receive',
    icon: LayoutGrid,
    component: Multi,
    usrpOnly: true,
  },
  { path: 'recordings', label: () => t('Aufnahmen'), group: 'data', icon: FileAudio, component: Recordings },
  { path: 'bookmarks', label: () => t('Lesezeichen'), group: 'data', icon: Bookmark, component: Bookmarks },
  { path: 'alerts', label: () => t('Alarme'), group: 'data', icon: BellRing, component: Alerts },
  {
    path: 'schedules',
    label: () => t('Zeitpläne'),
    group: 'system',
    icon: CalendarClock,
    component: Schedules,
  },
  { path: 'api', label: () => 'API', group: 'system', icon: SquareCode, component: ApiDocs },
];
