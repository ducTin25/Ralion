import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BellIcon,
  BookIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  CodeIcon,
  CommentDiscussionIcon,
  FileDirectoryIcon,
  FileIcon,
  FlagIcon,
  GearIcon,
  LockIcon,
  MoonIcon,
  OrganizationIcon,
  GraphIcon,
  SearchIcon,
  ShieldCheckIcon,
  SignOutIcon,
  SunIcon,
  SyncIcon,
  XIcon,
  type OcticonProps,
} from "@primer/octicons-react";
import type { ComponentType } from "react";

const ICONS = {
  logo: CheckIcon,
  check: CheckIcon,
  chat: CommentDiscussionIcon,
  flag: FlagIcon,
  arrow: ArrowRightIcon,
  back: ArrowLeftIcon,
  search: SearchIcon,
  sun: SunIcon,
  moon: MoonIcon,
  bell: BellIcon,
  close: XIcon,
  clock: ClockIcon,
  lock: LockIcon,
  document: FileIcon,
  chevron: ChevronRightIcon,
  chevronDown: ChevronDownIcon,
  refresh: SyncIcon,
  logout: SignOutIcon,
  building: OrganizationIcon,
  dashboard: GraphIcon,
  folder: FileDirectoryIcon,
  shield: ShieldCheckIcon,
  settings: GearIcon,
  code: CodeIcon,
  book: BookIcon,
} satisfies Record<string, ComponentType<OcticonProps>>;

export type MemberIconName = keyof typeof ICONS;

export function MemberIcon({ name, size = 16 }: { name: MemberIconName; size?: number }) {
  const Icon = ICONS[name];
  return <Icon aria-hidden="true" size={size} />;
}
