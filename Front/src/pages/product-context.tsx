import { createContext, useContext } from 'react'
import type { Entity } from '../api/types'
export interface ProductContextValue { product: Entity; productId: string; round: Entity | null; roundId?: string; writable: boolean; setTab:(tab:string)=>void; setRound:(id:string,nextTab?:string)=>void }
export const ProductContext=createContext<ProductContextValue|null>(null)
export function useProduct(){const context=useContext(ProductContext);if(!context)throw new Error('商品上下文缺失');return context}
