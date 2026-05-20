from fastapi import Header, HTTPException

async def get_use_native_sql(x_data_source: str = Header(default="orm")):
    """Header для выбора источника данных: 'orm' или 'native'"""
    if x_data_source not in ["orm", "native"]:
        raise HTTPException(status_code=400, detail="Invalid data source. Use 'orm' or 'native'")
    return x_data_source == "native"