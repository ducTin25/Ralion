import {
  AlertIcon as PrimerAlertIcon,
  CheckIcon as PrimerCheckIcon,
  ChevronRightIcon as PrimerChevronRightIcon,
  GraphIcon,
  SearchIcon as PrimerSearchIcon,
  XIcon as PrimerXIcon,
  type OcticonProps,
} from "@primer/octicons-react";

type IconProps = OcticonProps;

export function ChartIcon(props: IconProps) {
  return <GraphIcon aria-hidden="true" size={16} {...props} />;
}

export function SearchIcon(props: IconProps) {
  return <PrimerSearchIcon aria-hidden="true" size={16} {...props} />;
}

export function ChevronRightIcon(props: IconProps) {
  return <PrimerChevronRightIcon aria-hidden="true" size={16} {...props} />;
}

export function CheckIcon(props: IconProps) {
  return <PrimerCheckIcon aria-hidden="true" size={16} {...props} />;
}

export function AlertIcon(props: IconProps) {
  return <PrimerAlertIcon aria-hidden="true" size={16} {...props} />;
}

export function XIcon(props: IconProps) {
  return <PrimerXIcon aria-hidden="true" size={16} {...props} />;
}
