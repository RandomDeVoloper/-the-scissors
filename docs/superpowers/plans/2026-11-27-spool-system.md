# Spool Sistemi (Makara Mekaniği) — İmplementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BP_BabyDoll'a 3 makaralı spool sistemi ekle — her 15 saniyede bir rastgele dönen, el ile 25 Altın İğne harcayarak döndürülebilen ve aktif renge göre stat çarpanı uygulayan mekanik.

**Architecture:** BP_BabyDoll'a yeni bir SpoolComponent veya doğrudan variable seti eklenecek. Auto-spin için Blueprint Timer, stat uygulaması için mevcut multiplier değişkenleri (AbilityDamageMultiplier, speed vs.) kullanılacak. Para kalıcı olacak şekilde BP_SG_Player'a GoldNeedles integer eklenir.

**Tech Stack:** Unreal Engine 5.8 Blueprint, unreal-mcp araçları, mevcut Monster Tooth Survivors Template altyapısı.

**Spec:** `docs/superpowers/specs/2026-11-27-spool-system-design.md`

## Global Constraints

- Tüm değişiklikler Blueprint üzerinden yapılır, C++ kodu yazılmaz.
- Stat çarpanları mevcut template değişkenlerini kullanır (yeni stat sistemi icat etme).
- BP_BabyDoll BP_Base_Character'dan türetilmiştir; Base'e dokunulursa diğer karakterler etkilenir — değişiklikler BabyDoll'a özel tutulur.
- Auto-spin interval = 15 saniye (float sabiti olarak tutulacak, kolayca değiştirilebilir).
- Manuel spin maliyeti = 25 Altın İğne.
- Para koşu bitince sıfırlanmaz (BP_SG_Player'da kalıcı).
- 3 renk: Red/Blue/Yellow — her slot bağımsız, eşit 1/3 ihtimal.

## Review Focus

- HP negatif etki hesabı: Red/Blue kombinasyonu aynı anda aktifken mevcut HP > yeni maks HP olabilir; bunu handle etmeyen kod crash yerine clamp yapmalı.
- Spin animasyonu sırasında ölüm: 1.5 saniyelik animasyon bitince stat güncelleniyorsa, bu süre içinde ölünürse timer iptal edilmeli.
- Altın yetersizliği: manuel spin çağrıldığında para yoksa hiçbir şey yapılmamalı (sessiz fail, UI feedback).
- Jackpot tespiti: 3 slot kontrol edilirken uninitialized array erişimi mevcut template'de sık görüldü (WORKLOG); array bound check zorunlu.
- Save/Load round-trip: GoldNeedles değeri kaydedilip yüklendiğinde kaybolmamalı.

---

## Task 1: Enum ve Struct Oluşturma

**Files:**
- Create: `Content/SurvivorsTemplate/Blueprints/Enums/E_SpoolColor.uasset`
- Create: `Content/SurvivorsTemplate/Blueprints/Structs/ST_SpoolSlot.uasset`

**Interfaces:**
- Produces: `E_SpoolColor` (Red, Blue, Yellow değerleri), `ST_SpoolSlot` (Color: E_SpoolColor alanıyla struct)

- [ ] **Adım 1: E_SpoolColor enum'unu oluştur**

  unreal-mcp ile yeni Blueprint Enum oluştur:
  - Adı: `E_SpoolColor`
  - Yol: `Content/SurvivorsTemplate/Blueprints/Enums/`
  - Değerler: Red, Blue, Yellow

- [ ] **Adım 2: Enum'un kaydedildiğini doğrula**

  unreal-mcp ile Content Browser'da `E_SpoolColor`'ın göründüğünü kontrol et.

- [ ] **Adım 3: ST_SpoolSlot struct'ını oluştur**

  unreal-mcp ile yeni Blueprint Struct:
  - Adı: `ST_SpoolSlot`
  - Yol: `Content/SurvivorsTemplate/Blueprints/Structs/`
  - Alan: `Color` (E_SpoolColor tipi, default = Red)

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Enums/ Content/SurvivorsTemplate/Blueprints/Structs/
  git commit -m "feat: add E_SpoolColor enum and ST_SpoolSlot struct for spool system

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 2: BP_SG_Player'a Kalıcı Para Ekleme

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Saves/BP_SG_Player.uasset`

**Interfaces:**
- Consumes: —
- Produces: `GoldNeedles` (Integer, default=0) — kalıcı save variable

- [ ] **Adım 1: BP_SG_Player'ı aç**

  unreal-mcp ile `BP_SG_Player` Blueprint'ini aç.

- [ ] **Adım 2: GoldNeedles değişkeni ekle**

  Integer tipinde, adı `GoldNeedles`, default değer 0, `SaveGame` flag'i işaretli.

- [ ] **Adım 3: Compile ve save**

  Hata yoksa kaydet.

- [ ] **Adım 4: Doğrula**

  unreal-mcp Output Log'da compile hatası yoktur.

- [ ] **Adım 5: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Saves/
  git commit -m "feat: add persistent GoldNeedles currency to BP_SG_Player

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 3: BP_BabyDoll'a Spool State Ekleme

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset`

**Interfaces:**
- Consumes: `E_SpoolColor` (Task 1), `ST_SpoolSlot` (Task 1)
- Produces:
  - `SpoolSlots` — `Array of ST_SpoolSlot`, boyut 3, default her biri Red
  - `AutoSpinInterval` — Float, default 15.0
  - `ManualSpinCost` — Integer, default 25
  - `SpoolTimerHandle` — Timer Handle variable

- [ ] **Adım 1: BP_BabyDoll'ı aç**

  unreal-mcp ile `BP_BabyDoll` Blueprint'ini aç.

- [ ] **Adım 2: Spool değişkenlerini ekle**

  - `SpoolSlots`: Array of ST_SpoolSlot, varsayılan 3 eleman (hepsi Red)
  - `AutoSpinInterval`: Float = 15.0
  - `ManualSpinCost`: Integer = 25
  - `SpoolTimerHandle`: Timer Handle

- [ ] **Adım 3: Compile ve save**

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset
  git commit -m "feat: add spool state variables to BP_BabyDoll

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 4: SpinSpools Fonksiyonu ve Stat Uygulaması

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset`

**Interfaces:**
- Consumes: `SpoolSlots` (Task 3), `AbilityDamageMultiplier` ve movement speed (BP_Base_Character'dan gelen)
- Produces:
  - `SpinSpools()` — custom event (no params, no return)
  - `ApplySpoolStats()` — custom event (no params, no return)

Stat çarpanı tablosu (her slot için additive):

| Renk | SpeedMultiplier delta | DamageMultiplier delta | MaxHP delta |
|------|----------------------|------------------------|-------------|
| Red  | +0.15                | +0.20                  | −0.20       |
| Blue | −0.15                | −0.10                  | +0.30       |
| Yellow | 0                  | 0                      | 0 (krit/loot ayrı Task 5) |

Base değerler (1 slot Red iken): SpeedMultiplier=1.15, DamageMultiplier=1.20, MaxHP=0.80 × base.  
3 slot toplanarak hesap edilir. Örnek: 2× Red + 1× Blue → Speed=1.15, Damage=1.30, MaxHP=0.70.

- [ ] **Adım 1: SpinSpools custom event'ini oluştur**

  Mantık:
  1. SpoolSlots dizisini 3 kez iterate et
  2. Her slot için 0–2 arası random integer al → 0=Red, 1=Blue, 2=Yellow
  3. Slot'un Color alanını güncelle
  4. `ApplySpoolStats()` çağır

- [ ] **Adım 2: ApplySpoolStats custom event'ini oluştur**

  Mantık:
  1. SpeedDelta=0, DamageDelta=0, HPDelta=0 local float'ları başlat
  2. SpoolSlots'u iterate et, her renk için tablodaki delta'yı ekle
  3. Jackpot check: 3 slot aynı mı? Evet → delta'ları ×2 yap
  4. Karakter stats'ını güncelle (Base değer + delta):
     - `AbilityDamageMultiplier` = 1.0 + DamageDelta
     - Movement speed: `GetCharacterMovement → MaxWalkSpeed` = BaseSpeed × (1.0 + SpeedDelta)
     - MaxHP: `GetCharacterMovement`'ten bağımsız; HP component varsa MaxHP'yi set et, yoksa HP'yi (BaseMaxHP × (1.0 + HPDelta)) ile clamp et
  5. HP clamp: CurrentHP > yeni MaxHP ise CurrentHP = yeni MaxHP

  > **Builder note:** BaseSpeed ve BaseMaxHP'yi Event BeginPlay'de kaydet; Apply her çağrıldığında base'den hesapla (stack overflow önlemi).

- [ ] **Adım 3: Compile ve output log'u kontrol et**

  Array bound ve uninitialized variable uyarısı yoktur.

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset
  git commit -m "feat: implement SpinSpools and ApplySpoolStats in BP_BabyDoll

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 5: Auto-Spin Timer

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset`

**Interfaces:**
- Consumes: `SpinSpools` (Task 4), `AutoSpinInterval` (Task 3), `SpoolTimerHandle` (Task 3)
- Produces: Event BeginPlay'e timer başlatma logic'i

- [ ] **Adım 1: Event BeginPlay'e timer ekle**

  `Set Timer by Function Name`:
  - FunctionName: `SpinSpools`
  - Time: `AutoSpinInterval` (15.0)
  - Looping: true
  - Return → `SpoolTimerHandle`'a ata

  Ayrıca BeginPlay'de BaseSpeed ve BaseMaxHP'yi local değişkenlere kaydet (Task 4 için).

- [ ] **Adım 2: Event EndPlay'de timer'ı temizle**

  `Clear Timer by Handle` → `SpoolTimerHandle` ile.

- [ ] **Adım 3: PIE testi**

  unreal-mcp ile PIE başlat. 15 saniye bekle, Output Log'da SpinSpools'un çağrıldığını doğrula (Print String ekleyerek).

- [ ] **Adım 4: Print String'i kaldır, compile, commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset
  git commit -m "feat: add auto-spin timer (15s) to BP_BabyDoll BeginPlay

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 6: Manuel Spin (Para Harcama)

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset`

**Interfaces:**
- Consumes: `SpinSpools` (Task 4), `GoldNeedles` (Task 2 — BP_SG_Player üzerinden), `ManualSpinCost` (Task 3)
- Produces: `TryManualSpin()` custom event — UI/input tarafından çağrılır

- [ ] **Adım 1: TryManualSpin custom event'ini oluştur**

  Mantık:
  1. `Get Game Instance → Cast to BP_SG_Player` (ya da mevcut save sistemi nasıl erişiliyorsa aynı pattern'ı kullan — WORKLOG'da `BP_SG_Player` için kullanılan erişim şeklini takip et)
  2. `GoldNeedles >= ManualSpinCost` kontrol et
  3. Evet → `GoldNeedles -= ManualSpinCost`, save et, `SpinSpools()` çağır
  4. Hayır → sessiz fail (UI feedback Task 7'de)

- [ ] **Adım 2: Compile ve output log kontrolü**

- [ ] **Adım 3: PIE testi — altın olmadan çağır, hata yoktur**

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset
  git commit -m "feat: add TryManualSpin with gold cost check

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 7: HUD — Makara Göstergesi ve Para Sayacı

**Files:**
- Modify veya Create: `Content/SurvivorsTemplate/Blueprints/` altındaki HUD Widget (mevcut HUD hangisi ise — builder bunu bulacak)
- Modify: BP_BabyDoll (HUD'a event dispatch)

**Interfaces:**
- Consumes: `SpoolSlots` (Task 3), `GoldNeedles` (Task 2), Spin animasyon tetikleyicisi
- Produces: Görsel spool göstergesi (3 renkli ikon), altın sayacı, yetersiz altın feedback'i

- [ ] **Adım 1: Mevcut HUD Widget'ını bul**

  Content Browser'da oyun içi HUD'u bul (büyük olasılıkla `WBP_HUD` ya da benzeri).

- [ ] **Adım 2: 3 spool slot ikonu ekle**

  Her slot için Image widget — SpoolSlots'taki renge göre renk veya texture set edilir.  
  SpinSpools çağrıldığında HUD'daki ikonlar güncellenir (Event Dispatcher veya doğrudan HUD referansıyla).

- [ ] **Adım 3: Altın sayacı ekle**

  `GoldNeedles` değerini gösteren Text widget. TryManualSpin çağrıldıktan sonra güncellenir.

- [ ] **Adım 4: Yetersiz altın feedback'i**

  TryManualSpin'den "para yok" branch'ı HUD'a bir flash/shake efekti gönderir (1 saniyelik renk yanması yeterli).

- [ ] **Adım 5: PIE testi — 3 slot görünüyor, spin sonrası renkler değişiyor**

- [ ] **Adım 6: Compile ve commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/
  git commit -m "feat: add spool HUD widget with color indicators and gold counter

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 8: Düşman Drop — Altın İğne

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Enemies/BP_Base_Enemy.uasset` (ya da ölüm logic'i neredeyse)

**Interfaces:**
- Consumes: `GoldNeedles` (Task 2 — BP_SG_Player)
- Produces: Düşman ölümünde 1–5 arası random GoldNeedles drop

- [ ] **Adım 1: BP_Base_Enemy ölüm event'ini bul**

  unreal-mcp ile BP_Base_Enemy'de `OnDeath` veya benzeri event'i bul.

- [ ] **Adım 2: GoldNeedles drop logic'i ekle**

  Ölümde: `Random Integer in Range(1, 5)` → `BP_SG_Player.GoldNeedles +=` bu değer → save.

  > **Builder note:** BP_SG_Player'a erişim için mevcut template'in nasıl save game'e ulaştığına bak (büyük ihtimalle Game Instance veya Get Game Mode üzerinden). Aynı pattern'ı kullan.

- [ ] **Adım 3: PIE testi — düşman öldür, altın artar**

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Enemies/
  git commit -m "feat: add GoldNeedles drop on enemy death

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Task 9: Input Bağlama — Manuel Spin Tuşu

**Files:**
- Modify: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset` (input event)
- Modify veya Create: Input mapping (mevcut Action/Axis mapping şeması var — Enhanced Input yok)

**Interfaces:**
- Consumes: `TryManualSpin` (Task 6)
- Produces: Oyuncu belirli bir tuşa (öneri: **F** veya **Q**) basarak TryManualSpin'i tetikler

- [ ] **Adım 1: Input action belirle**

  Mevcut input sistemi (eski Action/Axis Mappings) üzerinden `ManualSpin` adında bir Action ekle (öneri: **F** tuşu).

- [ ] **Adım 2: BP_BabyDoll'a input event ekle**

  `InputAction ManualSpin` → Pressed → `TryManualSpin` çağır.

- [ ] **Adım 3: PIE testi — F'ye bas, altın varsa spin olur, yoksa olmaz**

- [ ] **Adım 4: Commit**

  ```bash
  git add Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset
  git commit -m "feat: bind F key to TryManualSpin for manual spool spin

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012nJEiiE2i4RVPGismoBV8e"
  ```

---

## Son Doğrulama

- [ ] 15 saniye bekle — tüm 3 makara rastgele döner, stat değişimi hissedilir.
- [ ] 25+ altın ile F tuşuna bas — spin olur, altın azalır.
- [ ] 0 altın ile F tuşuna bas — spin olmaz, HUD feedback görünür.
- [ ] 3 aynı renk gelince (Jackpot) stat bonusu 2× hissedilir.
- [ ] Oyunu kapat, aç — altın korunur.
