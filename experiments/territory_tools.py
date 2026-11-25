"""Strict contracts for optional territory feeds; absent feeds fail closed.

The tool specs are not exposed to the agent until their adapters are configured.
An adapter is responsible for provenance, freshness, and licensing of its data.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Callable, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


ShortText = Annotated[str, Field(min_length=1, max_length=120)]
OptionalText = ShortText | None
DatetimeText = Annotated[str, Field(min_length=19, max_length=35)]
DateText = Annotated[str, Field(pattern=r'^\d{4}-\d{2}-\d{2}$')]
Limit = Annotated[int, Field(ge=1, le=10)]


def _aware_iso(value: str | None) -> str | None:
    if value is not None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError('Invalid ISO-8601 datetime') from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('Datetime needs a UTC offset')
    return value


class PublicServices(Arguments):
    category: Literal['administration','consulate_embassy','police_safety','pharmacy_on_duty',
                      'hospital_clinic','museum_monument','convention_center',
                      'coworking_business_hub','transport_hub']
    query: OptionalText
    origin_label: OptionalText
    target_datetime_iso: DatetimeText | None
    pmr_accessible: bool | None
    language_spoken: Literal['fr','en','es','de','ar','zh'] | None
    limit: Limit

    @field_validator('target_datetime_iso')
    @classmethod
    def valid_datetime(cls, value):
        return _aware_iso(value)


class EntityDetails(Arguments):
    entity_id: ShortText
    source_registry: Literal['catalogue_chr','public_services','events_agenda']
    target_datetime_iso: DatetimeText | None

    @field_validator('target_datetime_iso')
    @classmethod
    def valid_datetime(cls, value):
        return _aware_iso(value)


class EventsAgenda(Arguments):
    start_date_iso: DateText
    end_date_iso: DateText
    event_type: Literal['trade_show_pro','cultural_exhibition','civic_public',
                        'sports','exceptional_closure'] | None
    query: OptionalText
    free_entry_only: bool | None
    limit: Limit

    @model_validator(mode='after')
    def valid_range(self):
        try:
            start, end = date.fromisoformat(self.start_date_iso), date.fromisoformat(self.end_date_iso)
        except ValueError:
            raise ValueError('Invalid calendar date') from None
        if start > end or (end-start).days > 31:
            raise ValueError('Event search date range must be between 0 and 31 days')
        return self


class TransitOptions(Arguments):
    origin_label: ShortText
    destination_label: ShortText
    departure_datetime_iso: DatetimeText | None
    wheelchair_accessible: bool
    modes: list[Literal['bus','regional_train','airport_shuttle']] | None

    @field_validator('departure_datetime_iso')
    @classmethod
    def valid_datetime(cls, value):
        return _aware_iso(value)

    @field_validator('modes')
    @classmethod
    def valid_modes(cls, value):
        if value is not None and (not value or len(value)>3 or len(value)!=len(set(value))):
            raise ValueError('Modes must be nonempty and unique')
        return value


class OfficialAlerts(Arguments):
    domains: Annotated[list[Literal['weather','air_quality','transit_disruption',
                                    'traffic_restriction','public_safety','health_advisory']],
                       Field(min_length=1,max_length=6)]
    area_label: OptionalText
    min_severity: Literal['info','advisory','warning','critical']

    @field_validator('domains')
    @classmethod
    def unique_domains(cls, value):
        if len(value)!=len(set(value)):
            raise ValueError('Duplicate alert domain')
        return value


class ProcedureRules(Arguments):
    procedure_topic: Literal['identity_passport','visa_business_entry','residency_civil_status',
                             'local_tax_tourist_tax',
                             'lost_stolen_documents','business_event_permit',
                             'public_transit_fares_passes']
    user_profile: Literal['citizen_resident','foreign_visitor',
                          'business_traveler','unknown']
    specific_question: OptionalText


MODELS = {
    'search_public_services': PublicServices,
    'get_entity_details': EntityDetails,
    'search_events_agenda': EventsAgenda,
    'get_transit_options': TransitOptions,
    'get_official_alerts': OfficialAlerts,
    'lookup_procedure_rules': ProcedureRules,
}

DESCRIPTIONS = {
    'search_public_services': 'Search a configured public-service directory. Never infer live opening, duty pharmacy, accessibility, or language from absent fields.',
    'get_entity_details': 'Read a specific entity previously returned by a configured registry. Unknown entity IDs are rejected.',
    'search_events_agenda': 'Search a configured dated event feed. An absent feed is unavailable, not an empty agenda.',
    'get_transit_options': 'Find bus, regional train or airport shuttle options from a configured Côte d’Ivoire feed. No live service or accessibility claim without explicit evidence. Metro and tram are not supported.',
    'get_official_alerts': 'Read configured active alerts with an explicit update time. No feed means unknown, not no alerts.',
    'lookup_procedure_rules': 'Look up a configured, dated rule. No legal eligibility inference when a rule or user profile is missing.',
}


def tool_spec(name: str) -> dict:
    if name not in MODELS:
        raise ValueError('Unknown territory tool')
    return {'type':'function','function':{'name':name,'description':DESCRIPTIONS[name],
            'strict':True,'parameters':MODELS[name].model_json_schema()}}


class TerritoryTools:
    """Only explicitly configured adapters are callable; no synthetic official data."""

    def __init__(self, adapters: dict[str, Callable[[Arguments, float], dict]] | None = None,
                 handoffs: dict[str,str] | None = None):
        self.adapters = adapters or {}
        if set(self.adapters)-MODELS.keys():
            raise ValueError('Unknown adapter')
        self.handoffs=handoffs or {}
        if any(not key or not isinstance(key,str) or not isinstance(url,str) or
               urlsplit(url).scheme!='https' or not urlsplit(url).hostname or
               urlsplit(url).username or urlsplit(url).password for key,url in self.handoffs.items()):
            raise ValueError('Handoff URL must be a configured HTTPS endpoint')
        self.seen: dict[tuple[str,str], dict] = {}

    def specs(self) -> list[dict]:
        return [tool_spec(name) for name in MODELS if name in self.adapters]

    def execute(self, name: str, raw: dict, timeout: float = 3) -> dict:
        if name not in MODELS:
            raise ValueError('Unknown territory tool')
        args = MODELS[name].model_validate(raw)
        if name == 'get_entity_details' and (args.source_registry,args.entity_id) not in self.seen:
            return {'status':'UNKNOWN_ENTITY','items':[]}
        adapter = self.adapters.get(name)
        if adapter is None:
            return {'status':'SERVICE_UNAVAILABLE','reason':'source_not_configured'}
        result = adapter(args, min(3, max(.1, timeout)))
        if not isinstance(result,dict) or result.get('status') not in ('ok','SERVICE_UNAVAILABLE','UNKNOWN_ENTITY'):
            raise ValueError('Invalid adapter response')
        if 'http://' in str(result).lower() or 'https://' in str(result).lower() or 'www.' in str(result).lower():
            raise ValueError('Adapter must return handoff IDs, not raw URLs')
        if result['status']=='ok':
            if not isinstance(result.get('source'),dict) or not result['source'].get('publisher') or not result['source'].get('updated_at'):
                raise ValueError('Successful result needs publisher and updated_at')
            items=result.get('items',[])
            if not isinstance(items,list) or len(items)>10 or any(not isinstance(x,dict) for x in items):
                raise ValueError('Invalid items')
            if any({'latitude','longitude','coordinates','geometry'} & item.keys() for item in items):
                raise ValueError('Coordinates stay in the application layer')
            registry={'search_public_services':'public_services','search_events_agenda':'events_agenda',
                      'get_entity_details':getattr(args,'source_registry',None)}.get(name)
            for item in items:
                if registry and isinstance(item.get('entity_id'),str):
                    self.seen[(registry,item['entity_id'])]=item
        return result
