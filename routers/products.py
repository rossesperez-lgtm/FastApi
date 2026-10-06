from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel


router = APIRouter(prefix="/products",
                   tags=["Productos"],
                   responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}})

products_list =["Producto 1", "Producto 2", "Producto 3", "Producto 4", "Producto 5"]

@router.get("/")
async def products():
    """Retorna el listado de productos."""
    return products_list

@router.get("/{id}")
async def get_product_by_id(id: int):
    """Retorna el producto por id."""
    return products_list[id]

