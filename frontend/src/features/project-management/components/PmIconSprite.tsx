import {
  AlertIcon,
  ArrowRightIcon,
  BellIcon,
  BookIcon,
  CheckCircleIcon,
  CheckIcon,
  ChevronDownIcon,
  ClockIcon,
  CreditCardIcon,
  EyeIcon,
  FileDirectoryIcon,
  FileIcon,
  FlagIcon,
  GraphIcon,
  KeyIcon,
  LockIcon,
  MoonIcon,
  PeopleIcon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  ShieldIcon,
  SignOutIcon,
  SunIcon,
  TrashIcon,
  XCircleIcon,
  XIcon,
  type OcticonProps,
} from "@primer/octicons-react";
import type { ComponentType } from "react";

import { RalionBrand } from "@/components/brand/RalionBrand";

export type PmIconName =
  | "logo"
  | "folder"
  | "users"
  | "grid"
  | "book"
  | "doc"
  | "life"
  | "plus"
  | "arrow"
  | "chevron-down"
  | "x"
  | "check2"
  | "coin"
  | "sun"
  | "moon"
  | "close-ring"
  | "alert"
  | "search"
  | "bell"
  | "check-circle"
  | "eye"
  | "trash"
  | "pencil"
  | "key"
  | "flag"
  | "shield"
  | "lock"
  | "logout";

const ICONS: Record<Exclude<PmIconName, "logo">, ComponentType<OcticonProps>> = {
  folder: FileDirectoryIcon,
  users: PeopleIcon,
  grid: GraphIcon,
  book: BookIcon,
  doc: FileIcon,
  life: ClockIcon,
  plus: PlusIcon,
  arrow: ArrowRightIcon,
  "chevron-down": ChevronDownIcon,
  x: XIcon,
  check2: CheckIcon,
  coin: CreditCardIcon,
  sun: SunIcon,
  moon: MoonIcon,
  "close-ring": XCircleIcon,
  alert: AlertIcon,
  search: SearchIcon,
  bell: BellIcon,
  "check-circle": CheckCircleIcon,
  eye: EyeIcon,
  trash: TrashIcon,
  pencil: PencilIcon,
  key: KeyIcon,
  flag: FlagIcon,
  shield: ShieldIcon,
  lock: LockIcon,
  logout: SignOutIcon,
};

type PmIconProps = {
  name: PmIconName;
  size?: number;
  className?: string;
};

/** Existing feature-local adapter retained to avoid duplicating its semantic PM icon names. */
export function PmIcon({ name, size = 16, className }: PmIconProps) {
  if (name === "logo") return <RalionBrand size={size} className={className} />;
  const Icon = ICONS[name];
  return <Icon aria-hidden="true" size={size} className={className} />;
}
