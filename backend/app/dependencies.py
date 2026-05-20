from fastapi import Header, HTTPException

async def get_data_source(
    x_data_source: str = Header(default="orm", alias="X-Data-Source")
):
    """Определяет источник данных: orm или native"""
    if x_data_source not in ["orm", "native"]:
        raise HTTPException(
            status_code=400, 
            detail="X-Data-Source must be 'orm' or 'native'"
        )
    return x_data_source

# Алиас для обратной совместимости
get_use_native_sql = get_data_source