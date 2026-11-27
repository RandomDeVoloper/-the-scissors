# Spool Sistemi (Makara Mekaniği) — Tasarım Belgesi

**Tarih:** 2026-11-27  
**Yazar:** Niyazi + Claude

---

## Niyet ve Neden

Bez bebeğin makası terzi atölyesinin kalbi; makaranın ipliği karakterin gücünü belirler. Oyunun görsel kimliğiyle (3 makaralı makas, slot makinesi çağrışımı) mekanik kimliği örtüşsün: her birkaç saniyede bir makaralar rastgele döner, aktif renge göre bebek farklı bir güç profili kazanır. Oyuncu hem şansla hem timing kararıyla mücadele eder.

---

## Hedefler

- **Hedef:** Koşu boyunca karakterin güç profili dinamik kalsın; aynı build iki koşuda farklı hissetsin.
- **Hedef:** Görsel + mekanik sinerji — makas üzerindeki 3 makaranın dönmesi hem estetik hem oynanış.
- **Hedef:** Ekonomik karar baskısı — altın harcayıp şimdi mi döndüreyim, yoksa bekleyeyim?
- **Hedef-dışı:** Kullanıcının hangi rengin geleceğini öngörmesi (döngüsel değil rastgele).
- **Anti-hedef:** Spinin savaş akışını donduran bir UI/pause ekranı göstermesi.

---

## Kısıtlar

- Unreal Engine 5.8, saf Blueprint (C++ modülü yok).
- Mevcut temel: Monster Tooth Survivors Template — BP_Abilities_Component üzerinde stat multiplierleri zaten var (`AbilityDamageMultiplier`, `AbilityTimerMultiplier`).
- Karakter: BP_BabyDoll (BP_Base_Character'dan türetilmiş).
- Şu an yoklar: dash, ayrık dalga sistemi, dalga arası dükkan.

---

## Yaklaşımlar

### A — Passive Stat Overlay (seçilen)
Her spool slotu bağımsız bir stat çarpanı verir. 3 slotun aktif rengi toplanarak karaktere uygulanır. Spin olduğunda yeni rastgele renkler atanır, stat multiplierleri anlık güncellenir. Savaş durmaz.

**Artı:** Template'in multiplier altyapısıyla doğrudan entegre. Hissettirmesi "sürekli kayma" — hafif kaotik, temaya uygun.  
**Eksi:** Tüm spooller aynı anda dönerse net etki çok ani değişebilir.

### B — Triggered Burst
Spin olduğunda yeni renk bir defaya mahsus burst efekti patlatır (anlık AoE, iyileşme vb.), sonra söner. Statları kalıcı değiştirmez.

**Artı:** Her spinin dramatik bir anı var.  
**Eksi:** Template'e daha çok yeni sistem gerektiriyor; stat-based sinerji (Brotato hissi) kaybolur. Reddedildi.

### C — Tek slot döner, diğerleri sabit
Her spinle sadece 1 rastgele slot değişir.

**Artı:** Daha az sert ani değişimler.  
**Eksi:** Oyuncu için daha az okunabilir; "hangisi döndü?" kafa karışıklığı. Reddedildi.

**Seçilen: A**

---

## Mekanik Tasarım (Yaklaşım A)

### Spool Renkleri ve Efektleri

Her slot bağımsız olarak Red/Blue/Yellow değerinden birini taşır. Aynı anda 3 slotun efektleri additive (toplamalı) olarak uygulanır.

| Renk | İsim | Pozitif Etki | Negatif Etki |
|------|------|-------------|-------------|
| Kırmızı 🔴 | Öfke (Rage) | Hareket hızı +%15, hasar +%20 | Maks HP −%20 |
| Mavi 🔵 | Dev Ölçek | Boyut +%25, maks HP +%30 | Hareket hızı −%15, hasar −%10 |
| Sarı 🟡 | Jackpot | Kritik şansı +%20, loot drop +%25 | — (saf bonus, denge için daha nadir gelecek şekilde ağırlık ayarı yapılabilir) |

**Jackpot (3 Aynı):** Tüm 3 slot aynı renk gelirse o rengin bonusu ×2 uygulanır, özel görsel efekt tetiklenir.

### Spin Zamanlaması

| Parametre | Değer (ilk tuning) | Kaynak |
|-----------|-------------------|--------|
| Auto-spin interval | 15 saniye | Niyazi |
| Manuel spin maliyeti | 25 Altın İğne | Niyazi |
| Spin süresi (animasyon) | 1.5 saniye | Tasarım kararı (Claude) |

Spin animasyonu sırasında savaş devam eder. Stat güncellenmesi animasyon bitince (yeni renkler oturduğunda) gerçekleşir.

### Rastgelelik

Her slot için 3 renk eşit ağırlıkla seçilir (1/3 ihtimal). İleride ağırlık tablosu eklenebilir (örn. Sarı daha nadir).

---

## Para Sistemi (İlk Katman)

Bu belgede yalnızca in-run para tanımlanmaktadır. Meta-progression (Nadir İplik, skill tree, kozmetikler) ayrı bir tasarım belgesinde ele alınacak.

**Altın İğne** — kalıcı para birimi (koşular arası birikir, sıfırlanmaz):
- Düşmanlar öldürülünce düşer (drop).
- Manuel spool spini için harcanır (25 Altın İğne/spin).
- Koşu bitince kaybolmaz — meta progression (skill tree, kozmetikler) için de bu para kullanılır.
- Dalga aralarında küçük dükkan varsa orada da harcanabilir (ileride).

---

## Açık Kalan Kararlar (Builder Calls)

Aşağıdakiler implementer'ın kendi takdirine bırakılmaktadır:

- Spool görsel animasyonu (makaraların dönüş efekti) için Blueprint Timeline mi, Niagara mı kullanılacak.
- HP negatif etki hesabı: mevcut HP > yeni maks HP olduğunda HP'yi yeni maksa mı çekecek, yoksa orantılı mı hesaplayacak.
- Spin animasyonu sırasında UI feedback'i (HUD'da sayaç mı, makara üzerinde titreşim mi).
