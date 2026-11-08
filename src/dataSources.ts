export interface DataSource {
  readonly id: string
  readonly label: string
  readonly publisher: string
  readonly period: string
  readonly url: string
  readonly method: string
  readonly limits: string
}

export const SOURCE_REGISTER_URL =
  'https://github.com/ketema/beacon-snap-cliff/blob/e1ad7f11e788b293cb638db67b4fe8f5ee0b1751/docs/data-sources.md'

export const DATA_SOURCES: readonly DataSource[] = [
  {
    id: 'DS-H1',
    label: 'ACS SNAP households',
    publisher: 'U.S. Census Bureau, supplied through DataKind Beacon',
    period: '2020 to 2024 ACS five-year estimates, S2201',
    url: 'https://api.census.gov/data/2024/acs/acs5/subject/groups/S2201.html',
    method: 'SNAP household counts and shares joined by census tract.',
    limits: 'Survey estimates. A tract share does not establish household eligibility.',
  },
  {
    id: 'DS-H2',
    label: 'ACS poverty',
    publisher: 'U.S. Census Bureau, supplied through DataKind Beacon',
    period: '2020 to 2024 ACS five-year estimates, S1701',
    url: 'https://api.census.gov/data/2024/acs/acs5/subject/groups/S1701.html',
    method: 'Poverty rates supply the regional high-poverty threshold.',
    limits: 'Rates are survey estimates. Missing values remain missing.',
  },
  {
    id: 'DS-H6',
    label: 'USDA food access',
    publisher: 'USDA Economic Research Service, supplied through DataKind Beacon',
    period: '2025 SRAM/FARA source package',
    url: 'https://www.ers.usda.gov/data-products/food-access-research-atlas',
    method:
      'Uses the supplied driving-distance low-income, low-access flag: half a mile in urban areas or 10 miles in rural areas.',
    limits: 'This grocery-access flag is separate from the pantry proximity sliders.',
  },
  {
    id: 'DS-X5',
    label: 'SBA business loans',
    publisher: 'U.S. Small Business Administration',
    period: 'Fiscal years 2010 to 2026; source snapshot September 30, 2026',
    url: 'https://data.sba.gov/dataset/7a-504-foia',
    method:
      '7(a) and 504 approvals were geocoded and summed by tract. Rates use the 2020 population.',
    limits:
      '6,994 loans were placed in the four counties. Only 89.9% of the 7,817 candidate addresses matched; some matched outside the area. Borrower mailing addresses can differ from business sites. These programs do not cover all business credit, and a low rate does not prove unmet credit need.',
  },
  {
    id: 'DS-X7b',
    label: 'ACS homes with no car',
    publisher: 'U.S. Census Bureau, retrieved through Census Reporter',
    period: '2020 to 2024 ACS five-year estimates, B08201',
    url: 'https://api.census.gov/data/2024/acs/acs5/groups/B08201.html',
    method: 'Households with no vehicle divided by all households.',
    limits:
      'A transportation proxy, not measured travel time or a validated substitute for missing CDC social-needs data.',
  },
  {
    id: 'DS-X28',
    label: 'ACS household income',
    publisher: 'U.S. Census Bureau',
    period: '2020 to 2024 ACS five-year estimates, S1901/B19013, in 2024 dollars',
    url: 'https://api.census.gov/data/2024/acs/acs5/groups/B19013.html',
    method:
      'Supplied S1901 values were checked against the official B19013 bulk file. The card shows the 90% margin of error.',
    limits:
      'Unavailable values and the $250,000+ lower bound are preserved. Prior-period estimates do not fill current missing values.',
  },
  {
    id: 'DS-X12',
    label: 'Second Harvest sites',
    publisher: 'Second Harvest Food Bank of Central Florida',
    period: 'Food Finder snapshot retrieved November 7, 2026',
    url: 'https://feedhopenow.org/find-help/food-finder/',
    method:
      '424 directory locations, including 247 inside the four counties. Sites outside those counties can still be nearby.',
    limits:
      'Partner sites only, not every food source. Hours can change; capacity is not provided. Redistribution permission was not obtained.',
  },
  {
    id: 'DS-X24',
    label: 'Census population',
    publisher: 'U.S. Census Bureau',
    period: 'April 1, 2020 Census, TIGER/Line block file for Florida',
    url: 'https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/',
    method:
      'Block populations are summed to tracts and used to calculate each tract’s population-weighted center.',
    limits:
      '2020 counts do not represent current population. Only tract totals are shown; the source includes privacy noise.',
  },
  {
    id: 'DS-X16b',
    label: 'FEMA risk',
    publisher: 'FEMA National Risk Index',
    period: 'Saved tract extract retrieved November 7, 2026',
    url: 'https://www.fema.gov/flood-maps/products-tools/national-risk-index',
    method: 'Risk and social-vulnerability ratings from the FEMA ArcGIS tract service.',
    limits:
      'Context indicators, not food-demand forecasts. This extract was not checked against the publisher’s bulk file.',
  },
  {
    id: 'DS-X15b',
    label: 'Tract boundaries',
    publisher: 'FEMA ArcGIS tract layer, using Census tract geography',
    period: '2020 tract boundaries; extract retrieved November 7, 2026',
    url: 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0',
    method: '489 tract polygons supply the map and exterior county boundaries.',
    limits: 'The water tract 12095990000 has no polygon and is listed separately.',
  },
  {
    id: 'DS-H7',
    label: 'CDC PLACES',
    publisher: 'Centers for Disease Control and Prevention, supplied through DataKind Beacon',
    period: '2025 source release',
    url: 'https://www.cdc.gov/places/',
    method: 'The supplied file was inspected for food and transportation social-needs indicators.',
    limits:
      'Those indicators are blank across Florida in this file. They are shown as missing, never zero.',
  },
  {
    id: 'DS-X3b',
    label: 'CBPP SNAP Tracker',
    publisher: 'Center on Budget and Policy Priorities, using USDA and state program data',
    period: 'Saved workbook updated October 21, 2026; Florida July 2025 compared with July 2026',
    url: 'https://www.cbpp.org/research/food-assistance/snap-tracker-people-are-losing-food-assistance-as-the-harmful-2025',
    method: 'The SNAP change is calculated from the saved monthly participation series.',
    limits: 'Statewide participation context. No tract-level SNAP-loss series is available.',
  },
  {
    id: 'DS-X9b',
    label: 'Feeding America estimates',
    publisher: 'Feeding America, Map the Meal Gap',
    period: '2024 data year, four county pages',
    url: 'https://map.feedingamerica.org/',
    method:
      'County food-insecurity estimates are summed across Orange, Seminole, Lake, and Osceola.',
    limits:
      'Modeled county estimates, not observed counts of people at pantry sites. Briefing totals are rounded for display.',
  },
]
