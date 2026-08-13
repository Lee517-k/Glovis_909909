from pycityproto.city.person.v2.motion_pb2 import Status

PROFILE_ATTRIBUTES = {
    "name": str(),
    "gender": str(),
    "age": float(),
    "education": str(),
    "skill": str(),
    "occupation": str(),
    "family_consumption": str(),
    "consumption": str(),
    "personality": str(),
    "income": float(),
    "currency": float(),
    "residence": str(),
    "race": str(),
    "city": str(),
    "religion": str(),
    "marital_status": str(),
    # add firm attributes   
    "industry": str(),
    "size": str(),
    "registered_capital": int(),
    "founded_year": int(),
    "company_size": str(),
    "company_type": str(),
    # "company_partner": list(),
    "location": str(),
    "main_product": str(),
    "annual_revenue": int(),
    "employee_count": int(),
    "stock_status": str(),
    "culture": str(),
    "ownership_type":str(),
    "stock_status":str(),
    "main_products":str(),
    "relative_products":str(),
    "company_name":str(),
    "products": list(),
    "product_stocks": list(),
    "available_materials":list(),
    "company_capacity":int(),
    "fund":int(),
    "inventory_system": dict(),
    "intelligence_level": int(),
    "level": int(),  # 添加企业层级字段
}

STATE_ATTRIBUTES = {
    # base
    "id": -1,
    "attribute": dict(),
    "home": dict(),
    "work": dict(),
    "headquarters":dict(),
    "schedules": [],
    "vehicle_attribute": dict(),
    "bus_attribute": dict(),
    "pedestrian_attribute": dict(),
    "bike_attribute": dict(),
    # motion
    "status": Status.STATUS_UNSPECIFIED,
    "position": dict(),
    "v": float(),
    "direction": float(),
    "activity": str(),
    "l": float(),
}

SELF_DEFINE_PREFIX = "self_define_"

TIME_STAMP_KEY = "_timestamp"
