#!/usr/bin/env python3
"""月度定投现金流规划 — 按实际扣款日精确计算
用法: python3 monthly_cashflow.py [年份]
"""
import calendar, datetime, sys

# ===== 定投配置(按实际扣款模式) =====
# 周五集中扣款: A500¥1000 + 红利低波¥500 + 港股红利¥500 + 恒科¥500 + 科创创业50¥500
FRIDAY_DCA = 3000
# 周四扣款: 创新药¥500
THURSDAY_DCA = 500
# 每日扣款(QDII): 建信纳指¥100 + 广发医疗¥100 + 南方纳指¥10 + 张坤¥10
DAILY_DCA = 220

# ===== 中国股市节假日（2026年，每年初需更新） =====
HOLIDAYS_2026 = {
    # 元旦 1/1-1/3 (1/3周六, 只扣1/1-1/2)
    datetime.date(2026, 1, 1), datetime.date(2026, 1, 2),
    # 春节 2/17-2/23 (2/16除夕)
    datetime.date(2026, 2, 16), datetime.date(2026, 2, 17),
    datetime.date(2026, 2, 18), datetime.date(2026, 2, 19),
    datetime.date(2026, 2, 20), datetime.date(2026, 2, 23),
    # 清明 4/4-4/6 (4/4-5周六日, 扣4/6)
    datetime.date(2026, 4, 6),
    # 劳动节 5/1-5/5 (5/2-3周六日, 扣5/1,5/4,5/5)
    datetime.date(2026, 5, 1), datetime.date(2026, 5, 4), datetime.date(2026, 5, 5),
    # 端午 6/19-6/21 (6/20-21周六日, 扣6/19)
    datetime.date(2026, 6, 19),
    # 中秋 9/25 (国庆前)
    datetime.date(2026, 9, 25),
    # 国庆+中秋连休 10/1-10/8
    datetime.date(2026, 10, 1), datetime.date(2026, 10, 2),
    datetime.date(2026, 10, 5), datetime.date(2026, 10, 6),
    datetime.date(2026, 10, 7), datetime.date(2026, 10, 8),
}



def compute(year):
    holidays = HOLIDAYS_2026 if year == 2026 else set()
    result = []
    for m in range(1, 13):
        fridays = 0; thursdays = 0; total_days = 0
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            dt = datetime.date(year, m, d)
            if dt not in holidays and dt.weekday() < 5:
                total_days += 1
                if dt.weekday() == 4: fridays += 1
                if dt.weekday() == 3: thursdays += 1
        monthly = fridays * FRIDAY_DCA + thursdays * THURSDAY_DCA + total_days * DAILY_DCA
        result.append((m, total_days, fridays, thursdays, monthly))
    return result
year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
data = compute(year)

annual = sum(r[4] for r in data)
total_days = sum(r[1] for r in data)
total_fri = sum(r[2] for r in data)
total_thu = sum(r[3] for r in data)

print(f"# {year}年月度定投现金流规划（精确版）")
print()
print(f"| 扣款模式 | 金额 | 频率 | 备注 |")
print(f"|------|:---:|------|------|")
print(f"| A股+港股周定投 | ¥{FRIDAY_DCA:,} | 每周五 | A500¥1000+红利¥500+港股红利¥500+恒科¥500+科创创业50¥500 |")
print(f"| 创新药周定投 | ¥{THURSDAY_DCA} | 每周四 | 创新药精选50联接A |")
print(f"| QDII+张坤日定投 | ¥{DAILY_DCA} | 每日 | 纳指¥100+医疗¥100+南方纳指¥10+张坤¥10 |")
print()
print(f"全年: {total_days}个交易日, {total_fri}个周五, {total_thu}个周四, 总投入 **¥{annual:,}**")
print()
print("| 月份 | 交易日 | 周五 | 周四 | 周定投(周末) | 日定投(每日) | **当月合计** | 工资参考(2万) |")
print("|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
for m, days, fri, thu, amt in data:
    weekly_amt = fri * FRIDAY_DCA + thu * THURSDAY_DCA
    daily_amt = days * DAILY_DCA
    pct = amt / 20000
    print(f"| {m}月 | {days}天 | {fri}个 | {thu}个 | ¥{weekly_amt:,} | ¥{daily_amt:,} | **¥{amt:,}** | {pct:.0%} |")

print()
print("## 每周现金流速")
print()
print("| 周一～周三 | 周四 | 周五 |")
print("|------|------|------|")
print(f"| ¥{DAILY_DCA}(QDII+张坤) | ¥{DAILY_DCA+THURSDAY_DCA}(+创新药) | ¥{DAILY_DCA+FRIDAY_DCA:,}(+A股港股5只) |")
print(f"| 常规日 | 定投日 | **大额日** |")
print()
print("💡 周五扣款最重(¥3,220)，确保余额充足。周四次之(¥720)。")
print(f"💡 年化等效 ¥{(annual/total_days):.0f}/日 (vs 简化¥920/日)")
print(f"⚠️ 节假日为{year}年手动维护，每年初需更新脚本。QDII在A股休市时支付宝可能不扣款，表中按A股交易日保守估算。")