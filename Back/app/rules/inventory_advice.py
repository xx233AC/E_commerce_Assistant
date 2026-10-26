def inventory_values(stock_qty, warning_threshold):
    return {'stock_qty': stock_qty, 'locked_qty': 0, 'available_qty': stock_qty,
            'warning_threshold': warning_threshold, 'is_low_stock': stock_qty <= warning_threshold}


def advice_item(row, horizon_days=7):
    shortage = max(row['warning_threshold'] - row['available_qty'], 0)
    message = (f'当前可用库存 {row["available_qty"]}，已达到预警阈值 {row["warning_threshold"]}；'
               f'请在未来 {horizon_days} 天内核查补货安排，补至阈值至少需要 {shortage} 件。'
               if row['is_low_stock'] else
               f'当前可用库存 {row["available_qty"]} 高于预警阈值 {row["warning_threshold"]}，继续观察。')
    return {'sku_id': row['sku_id'], 'available_qty': row['available_qty'],
            'warning_threshold': row['warning_threshold'], 'suggestion': message, 'basis': 'threshold_rule'}
