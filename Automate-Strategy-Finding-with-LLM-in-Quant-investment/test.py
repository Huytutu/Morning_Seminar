from vnstock import Vnstock
stock = Vnstock().stock(symbol='VCI', source='VCI')
# Bảng cân đối kế toán - năm
stock.finance.balance_sheet(period='year', lang='vi', dropna=True)                                                                                                                                          
# Bảng cân đối kế toán - quý
stock.finance.balance_sheet(period='quarter', lang='en', dropna=True)
# Kết quả hoạt động kinh doanh
stock.finance.income_statement(period='year', lang='vi', dropna=True)
# Lưu chuyển tiền tệ
stock.finance.cash_flow(period='year', dropna=True)
# Chỉ số tài chính
stock.finance.ratio(period='year', lang='vi', dropna=True)