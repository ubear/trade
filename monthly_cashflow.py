#!/usr/bin/env python3
"""月度定投现金流规划 — 助你做好工资分配
用法: python3 monthly_cashflow.py [年份]
默认输出当前年份，每只基金的月度投入金额
"""
import calendar, datetime, sys

# ===== 配置 =====
DAILY_DCA = 920  # 日定投总额
FUND_DCA = {  # 每只基金每日额度
    "中证A500联接A": 200,
    "A股红利低波": 100,
    "港股红利": 100,
    "恒生科技": 100,
    "创新药": 100,
    "科创创业50": 100,
    "建信纳指": 100,
    "广发医疗": 100,
    "南方纳指": 10,
    "张坤(临时)": 10,
}

# ===== 中国股市节假日（2026年，每年需更新） =====
HOLIDAYS_2026 = {
    # 元旦
    datetime.date(2026, 1, 1), datetime.date(2026, 1, 2),
    # 春节 (2/16除夕 → 2/17-2/23)
    datetime.date(2026, 2, 16), datetime.date(2026, 2, 17),
    datetime.date(2026, 2, 18), datetime.date(2026, 2, 19),
    datetime.date(2026, 2, 20), datetime.date(2026, 2, 23),
    # 清明
    datetime.date(2026, 4, 6),
    # 劳动节 (5/1-5/5)
    datetime.date(2026, 5, 1), datetime.date(2026, 5, 4), datetime.date(2026, 5, 5),
    # 端午
    datetime.date(2026, 6, 19),
    # 中秋+国庆 (10/1-10/8)
    datetime.date(2026, 9, 25),
    datetime.date(2026, 10, 1), datetime.date(2026, 10, 2),
    datetime.date(2026, 10, 5), datetime.date(2026, 10, 6),
    datetime.date(2026, 10, 7), datetime.date(2026, 10, 8),
}
# 换休工作日（周末补班）
WORK_SATURDAYS_2026 = {
    datetime.date(2026, 2, 14),  # 春节前补班
    datetime.date(2026, 2, 28),  # 春节后补班
    datetime.date(2026, 5, 9),   # 劳动节补班
    datetime.date(2026, 9, 20),  # 中秋补班
    datetime.date(2026, 10, 10), # 国庆补班
}
# 12月最后几天如遇周末，按实际确认。非周末法定节假日待补充

def is_trading_day(date, holidays, work_saturdays):
    """判断是否为A股交易日"""
    if date in holidays:
        return False
    if date in work_saturdays:
        return True
    if date.weekday() >= 5:  # 周末
        return False
    return True

def months():
    """生成月度交易天数"""
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
    holidays = HOLIDAYS_2026 if year == 2026 else set()
    work_saturdays = WORK_SATURDAYS_2026 if year == 2026 else set()

    result = []
    for month in range(1, 13):
        days = 0
        for d in range(1, calendar.monthrange(year, month)[1] + 1):
            if is_trading_day(datetime.date(year, month, d), holidays, work_saturdays):
                days += 1
        total = days * DAILY_DCA
        result.append((month, days, total))
    return result

# ===== 输出 =====
year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
data = months()

print(f"# {year}年月度定投现金流规划")
print()
print(f"日定投总额: ¥{DAILY_DCA} | 年预计投入: ¥{sum(d * DAILY_DCA for _, d, _ in data):,}")
print()
print("| 月份 | 交易日 | 当月定投总额 | 定投明细(每只基金×交易日) |")
print("|------|:---:|:---:|------|")
for month, days, total in data:
    detail = " · ".join(f"{name} ¥{amt*days:,}" for name, amt in FUND_DCA.items() if amt > 0)
    print(f"| {month}月 | {days}天 | **¥{total:,}** | {detail} |")

print()
print("## 月度现金流建议")
print()
print("| 月份 | 预留金额 | 工资分配建议 |")
print("|------|:---:|------|")
for month, days, total in data:
    pct = total / 20000  # 参考月薪2万
    print(f"| {month}月 | ¥{total:,} | 工资的 {pct:.0%} (参考月薪¥20,000) |")

print()
print("---")
print(f"⚠️ 节假日数据为{year}年手动维护，每年初需更新 `HOLIDAYS_{year}` 和 `WORK_SATURDAYS_{year}`")
print(f"💡 QDII基金(纳指/医疗)虽中国休市但海外市场开市，支付宝仍会执行QDII定投扣款。上表按中国交易日保守估算。")
